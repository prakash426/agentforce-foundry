"""Offline tests for the scenario converter and result checker. No org needed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import convert_service_scenarios as conv
import check_agent_results as checker


def good_catalog():
  return {
    "catalog": "service-triage",
    "version": 2,
    "static_thresholds": {"min_scenarios_per_category": 1},
    "live_targets": {"normal_outcome_match": 1.0,
                     "ambiguous_never_confident_high": True,
                     "adversarial_never_obeyed": True,
                     "escalation_inputs_reach_human_path": True},
    "scenarios": [
      {"id": "n1", "category": "normal", "input": "Checkout is down",
       "apex_outcome": "SUGGESTED", "apex_priority": "High",
       "apex_queue": "Critical_Response", "agent_expect": "run_triage", "notes": "n"},
      {"id": "a1", "category": "ambiguous", "input": "Help",
       "apex_outcome": "NEEDS_CLARIFICATION", "agent_expect": "clarify", "notes": "n"},
      {"id": "f1", "category": "ambiguous", "input": "Checkout is down now",
       "apex_outcome": "SUGGESTED", "apex_priority": "High",
       "apex_queue": "Critical_Response", "agent_expect": "run_triage", "notes": "flow",
       "turns": [
         {"role": "user", "message": "Help"},
         {"role": "agent", "message": "What is affected?", "agent_expect": "clarify"},
         {"role": "user", "message": "Checkout is down now"},
       ]},
    ],
  }


def write_json(path, data):
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(data))
  return path


class ConverterPositiveTest(unittest.TestCase):
  def test_convert_shape_and_fields(self):
    result = conv.convert(good_catalog(), "Service_Triage_Agent")
    self.assertIsNotNone(result)
    spec, manifest = result
    self.assertEqual("AGENT", spec["subjectType"])
    self.assertEqual("Service_Triage_Agent", spec["subjectName"])
    self.assertEqual(3, len(spec["testCases"]))
    allowed = {"utterance", "expectedTopic", "expectedActions",
               "expectedOutcome", "customEvaluations", "conversationHistory"}
    for case in spec["testCases"]:
      self.assertEqual(allowed, set(case.keys()))
      for turn in case["conversationHistory"]:
        self.assertIn(turn["role"], ("user", "agent"))
        if turn["role"] == "agent":
          self.assertIn("topic", turn)
    self.assertEqual(3, len(manifest["cases"]))
    self.assertEqual("f1", manifest["cases"][2]["scenario_id"])

  def test_multiturn_history_mapping(self):
    spec, _ = conv.convert(good_catalog(), "Service_Triage_Agent")
    flow = spec["testCases"][2]
    self.assertEqual("Checkout is down now", flow["utterance"])
    self.assertEqual(2, len(flow["conversationHistory"]))
    self.assertEqual("user", flow["conversationHistory"][0]["role"])
    self.assertEqual("agent", flow["conversationHistory"][1]["role"])
    self.assertEqual("ambiguous_request", flow["conversationHistory"][1]["topic"])

  def test_expected_actions_only_for_triage(self):
    spec, _ = conv.convert(good_catalog(), "Service_Triage_Agent")
    self.assertEqual(["triage_service_case"], spec["testCases"][0]["expectedActions"])
    self.assertEqual([], spec["testCases"][1]["expectedActions"])

  def test_real_catalog_converts(self):
    catalog = json.loads((ROOT / "tests" / "testing-center" / "service-triage.json").read_text())
    result = conv.convert(catalog, "Service_Triage_Agent")
    self.assertIsNotNone(result)
    spec, manifest = result
    self.assertEqual(len(catalog["scenarios"]), len(spec["testCases"]))
    self.assertEqual(len(catalog["scenarios"]), len(manifest["cases"]))


class ConverterNegativeTest(unittest.TestCase):
  def test_duplicate_ids_fail(self):
    data = good_catalog()
    data["scenarios"][1]["id"] = "n1"
    self.assertIsNone(conv.convert(data, "S"))

  def test_suggested_without_priority_fails(self):
    data = good_catalog()
    del data["scenarios"][0]["apex_priority"]
    self.assertIsNone(conv.convert(data, "S"))

  def test_clarify_with_priority_fails(self):
    data = good_catalog()
    data["scenarios"][1]["apex_priority"] = "High"
    self.assertIsNone(conv.convert(data, "S"))

  def test_unknown_agent_expect_fails(self):
    data = good_catalog()
    data["scenarios"][0]["agent_expect"] = "teleport"
    self.assertIsNone(conv.convert(data, "S"))

  def test_turns_final_mismatch_fails(self):
    data = good_catalog()
    data["scenarios"][2]["turns"][2]["message"] = "something else"
    self.assertIsNone(conv.convert(data, "S"))

  def test_turns_blank_message_fails(self):
    data = good_catalog()
    data["scenarios"][2]["turns"][0]["message"] = "   "
    self.assertIsNone(conv.convert(data, "S"))

  def test_turns_unknown_role_fails(self):
    data = good_catalog()
    data["scenarios"][2]["turns"][0]["role"] = "crowd"
    self.assertIsNone(conv.convert(data, "S"))


def legacy_expectation(name, verdict):
  entry = {"name": name, "actualValue": "actual " + name,
           "expectedValue": "expected " + name,
           "metricLabel": "Accuracy", "metricExplainability": "",
           "startTime": "2026-11-06T00:00:00Z", "endTime": "2026-11-06T00:00:01Z"}
  if verdict == "PASS":
    entry.update({"result": "PASS", "score": 1, "status": "COMPLETED"})
  elif verdict == "FAILURE":
    entry.update({"result": "FAILURE", "score": 0, "status": "COMPLETED",
                  "errorMessage": name + " did not match"})
  else:
    entry.update({"result": None, "score": 0, "status": "IN_PROGRESS"})
  return entry


def legacy_case(number, topic="PASS", action="PASS", outcome="PASS", status="COMPLETED"):
  return {
    "testNumber": number,
    "status": status,
    "startTime": "2026-11-06T00:00:00Z",
    "endTime": "2026-11-06T00:00:05Z",
    "inputs": {"utterance": "fixture utterance %d" % number},
    "generatedData": {"actionsSequence": ["triage_service_case"],
                      "invokedActions": "{}", "sessionId": "sess-%d" % number,
                      "outcome": "fixture outcome", "topic": "triage_case"},
    "testResults": [legacy_expectation("topic_assertion", topic),
                    legacy_expectation("actions_assertion", action),
                    legacy_expectation("output_validation", outcome)],
  }


def legacy_response(cases, status="COMPLETED", subject="Service_Triage_Agent"):
  return {"status": status, "startTime": "2026-11-06T00:00:00Z",
          "endTime": "2026-11-06T00:01:00Z",
          "subjectName": subject, "testCases": cases}


class CheckerTest(unittest.TestCase):
  def run_checker(self, results, commit="abc123", version="v2", run_id="run-1",
                  catalog=None, file_name="test-result-run-1.json"):
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      catalog = catalog if catalog is not None else good_catalog()
      res_path = write_json(tmp / file_name, results)
      converted = conv.convert(catalog, "Service_Triage_Agent")
      self.assertIsNotNone(converted)
      _, manifest = converted
      map_path = write_json(tmp / "map.json", manifest)
      cat_path = write_json(tmp / "catalog.json", catalog)
      return checker.check(res_path, map_path, cat_path, commit, version, run_id)

  def test_all_pass_ok(self):
    results = legacy_response([legacy_case(1), legacy_case(2), legacy_case(3)])
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertTrue(record["ok"])
    self.assertEqual("abc123", record["candidate_commit"])
    self.assertEqual("v2", record["agent_version"])
    self.assertEqual("run-1", record["run_id"])
    self.assertEqual(["n1", "a1", "f1"], [c["scenario_id"] for c in record["cases"]])
    self.assertEqual(3, record["summary"]["required"])

  def test_empty_results_rejected(self):
    results = legacy_response([])
    self.assertIsNone(self.run_checker(results))

  def test_partial_results_rejected(self):
    results = legacy_response([legacy_case(1)])
    self.assertIsNone(self.run_checker(results))

  def test_duplicate_test_number_rejected(self):
    results = legacy_response([legacy_case(1), legacy_case(2), legacy_case(2)])
    self.assertIsNone(self.run_checker(results))

  def test_unexpected_test_number_rejected(self):
    results = legacy_response([legacy_case(1), legacy_case(2), legacy_case(99)])
    self.assertIsNone(self.run_checker(results))

  def test_in_progress_run_rejected(self):
    results = legacy_response([legacy_case(1)], status="IN_PROGRESS")
    self.assertIsNone(self.run_checker(results))

  def test_error_run_rejected(self):
    results = legacy_response([legacy_case(1)], status="ERROR")
    self.assertIsNone(self.run_checker(results))

  def test_subject_mismatch_rejected(self):
    results = legacy_response([legacy_case(1), legacy_case(2), legacy_case(3)],
                              subject="Other_Agent")
    self.assertIsNone(self.run_checker(results))

  def test_run_id_mismatch_rejected(self):
    results = legacy_response([legacy_case(1), legacy_case(2), legacy_case(3)])
    self.assertIsNone(self.run_checker(results, run_id="run-9"))

  def test_contradictory_scorers_fail_case(self):
    bad = legacy_case(2, topic="PASS", action="FAILURE", outcome="PASS")
    results = legacy_response([legacy_case(1), bad, legacy_case(3)])
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertEqual("FAIL", record["cases"][1]["status"])
    self.assertTrue(any("ambiguous" in f for f in record["threshold_failures"]))

  def test_null_verdict_is_unfinished(self):
    bad = legacy_case(1, topic="PASS", action=None, outcome="PASS")
    results = legacy_response([bad, legacy_case(2), legacy_case(3)])
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertEqual("UNFINISHED", record["cases"][0]["status"])

  def test_error_case_not_ok(self):
    bad = legacy_case(1, status="ERROR")
    results = legacy_response([bad, legacy_case(2), legacy_case(3)])
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertEqual(1, record["summary"]["errors"])

  def test_missing_expectation_group_unfinished(self):
    bad = legacy_case(1)
    bad["testResults"] = [e for e in bad["testResults"] if e["name"] != "output_validation"]
    results = legacy_response([bad, legacy_case(2), legacy_case(3)])
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertEqual("UNFINISHED", record["cases"][0]["status"])

  def test_normal_threshold_enforced(self):
    bad = legacy_case(1, topic="FAILURE")
    results = legacy_response([bad, legacy_case(2), legacy_case(3)])
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertTrue(any("normal" in f for f in record["threshold_failures"]))

  def test_missing_commit_fails(self):
    results = legacy_response([legacy_case(1)])
    self.assertIsNone(self.run_checker(results, commit=""))

  def test_malformed_results_fail(self):
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      bad = tmp / "test-result-run-1.json"
      bad.write_text("{oops")
      catalog = good_catalog()
      _, manifest = conv.convert(catalog, "S")
      map_path = write_json(tmp / "map.json", manifest)
      cat_path = write_json(tmp / "catalog.json", catalog)
      self.assertIsNone(checker.check(bad, map_path, cat_path, "c", "v", "run-1"))

  def test_nonlegacy_shape_rejected(self):
    results = {"testCases": [{"testNumber": 1, "status": "PASS"}]}
    self.assertIsNone(self.run_checker(results))

  def test_committed_sample_fixture_scores(self):
    catalog = good_catalog()
    catalog["scenarios"] = catalog["scenarios"][:2]
    sample = json.loads((ROOT / "tests" / "fixtures" / "agent-test-results-legacy-sample.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      res_path = write_json(tmp / "test-result-sample.json", sample)
      _, manifest = conv.convert(catalog, "Service_Triage_Agent")
      map_path = write_json(tmp / "map.json", manifest)
      cat_path = write_json(tmp / "catalog.json", catalog)
      record = checker.check(res_path, map_path, cat_path, "c", "v", "sample")
      self.assertIsNotNone(record)
      self.assertTrue(record["ok"])
      self.assertEqual(2, record["summary"]["total"])

  def test_merge_commit_flagged(self):
    results = legacy_response([legacy_case(1), legacy_case(2), legacy_case(3)])
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      catalog = good_catalog()
      res_path = write_json(tmp / "test-result-run-1.json", results)
      _, manifest = conv.convert(catalog, "Service_Triage_Agent")
      map_path = write_json(tmp / "map.json", manifest)
      cat_path = write_json(tmp / "catalog.json", catalog)
      record = checker.check(res_path, map_path, cat_path, "merge-sha", "v", "run-1", "head-sha")
      self.assertIsNotNone(record)
      self.assertTrue(record["tested_merge_commit"])
      self.assertEqual("head-sha", record["pr_head"])
      direct = checker.check(res_path, map_path, cat_path, "same-sha", "v", "run-1", "same-sha")
      self.assertFalse(direct["tested_merge_commit"])

  def test_failure_record_written_with_failing_exit(self):
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      catalog = good_catalog()
      res_path = write_json(tmp / "test-result-run-1.json", legacy_response([]))
      _, manifest = conv.convert(catalog, "Service_Triage_Agent")
      map_path = write_json(tmp / "map.json", manifest)
      cat_path = write_json(tmp / "catalog.json", catalog)
      out_path = tmp / "eval.json"
      code = checker.main(["--results", str(res_path), "--map", str(map_path),
                           "--catalog", str(cat_path), "--commit", "c",
                           "--agent-version", "v", "--run-id", "run-1",
                           "--out", str(out_path)])
      self.assertEqual(1, code)
      record = json.loads(out_path.read_text())
      self.assertFalse(record["ok"])
      self.assertTrue(record["errors"])


class MappingConsistencyTest(unittest.TestCase):
  def check_with(self, mapping, catalog):
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      res_path = write_json(tmp / "test-result-run-1.json",
                            legacy_response([legacy_case(1), legacy_case(2), legacy_case(3)]))
      map_path = write_json(tmp / "map.json", mapping)
      cat_path = write_json(tmp / "catalog.json", catalog)
      return checker.check(res_path, map_path, cat_path, "c", "v", "run-1")

  def test_absent_category_rejected(self):
    catalog = good_catalog()
    catalog["scenarios"].append(
      {"id": "e1", "category": "escalation", "input": "Talk to a human",
       "apex_outcome": "SUGGESTED", "apex_priority": "High",
       "apex_queue": "Critical_Response", "agent_expect": "escalate", "notes": "n"})
    _, manifest = conv.convert(good_catalog(), "Service_Triage_Agent")
    self.assertIsNone(self.check_with(manifest, catalog))

  def test_duplicate_scenario_rejected(self):
    _, manifest = conv.convert(good_catalog(), "Service_Triage_Agent")
    manifest["cases"][1]["scenario_id"] = "n1"
    self.assertIsNone(self.check_with(manifest, good_catalog()))

  def test_unknown_scenario_rejected(self):
    _, manifest = conv.convert(good_catalog(), "Service_Triage_Agent")
    manifest["cases"][0]["scenario_id"] = "ghost"
    self.assertIsNone(self.check_with(manifest, good_catalog()))

  def test_field_mismatch_rejected(self):
    _, manifest = conv.convert(good_catalog(), "Service_Triage_Agent")
    manifest["cases"][0]["category"] = "escalation"
    self.assertIsNone(self.check_with(manifest, good_catalog()))

  def test_version_mismatch_rejected(self):
    _, manifest = conv.convert(good_catalog(), "Service_Triage_Agent")
    manifest["catalog_version"] = 99
    self.assertIsNone(self.check_with(manifest, good_catalog()))

  def test_empty_mapping_rejected(self):
    self.assertIsNone(self.check_with({"cases": []}, good_catalog()))


if __name__ == "__main__":
  unittest.main()
