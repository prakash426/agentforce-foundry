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


class CheckerTest(unittest.TestCase):
  def run_checker(self, results, commit="abc123", version="v2"):
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      catalog = good_catalog()
      res_path = write_json(tmp / "results.json", results)
      spec, manifest = conv.convert(catalog, "Service_Triage_Agent")
      map_path = write_json(tmp / "map.json", manifest)
      cat_path = write_json(tmp / "catalog.json", catalog)
      out_path = tmp / "eval.json"
      record = checker.check(res_path, map_path, cat_path, commit, version, "run-1")
      return record

  def test_all_pass_ok(self):
    results = {"runId": "run-1", "subjectName": "Service_Triage_Agent", "testCases": [
      {"testNumber": 1, "status": "PASS"},
      {"testNumber": 2, "status": "PASS"},
      {"testNumber": 3, "status": "PASS"},
    ]}
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertTrue(record["ok"])
    self.assertEqual("abc123", record["candidate_commit"])
    self.assertEqual("v2", record["agent_version"])
    self.assertEqual(["n1", "a1", "f1"], [c["scenario_id"] for c in record["cases"]])

  def test_failed_case_not_ok(self):
    results = {"runId": "run-1", "testCases": [
      {"testNumber": 1, "status": "PASS"},
      {"testNumber": 2, "status": "FAIL", "message": "wrong topic"},
      {"testNumber": 3, "status": "PASS"},
    ]}
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertTrue(any("ambiguous" in f for f in record["threshold_failures"]))

  def test_error_status_not_ok(self):
    results = {"runId": "run-1", "testCases": [
      {"testNumber": 1, "status": "ERROR"},
      {"testNumber": 2, "status": "PASS"},
      {"testNumber": 3, "status": "PASS"},
    ]}
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertEqual(1, record["summary"]["errors"])

  def test_normal_threshold_enforced(self):
    results = {"runId": "run-1", "testCases": [
      {"testNumber": 1, "status": "FAIL"},
      {"testNumber": 2, "status": "PASS"},
      {"testNumber": 3, "status": "PASS"},
    ]}
    record = self.run_checker(results)
    self.assertIsNotNone(record)
    self.assertFalse(record["ok"])
    self.assertTrue(any("normal" in f for f in record["threshold_failures"]))

  def test_missing_commit_fails(self):
    results = {"runId": "run-1", "testCases": [{"testNumber": 1, "status": "PASS"}]}
    self.assertIsNone(self.run_checker(results, commit=""))

  def test_unmapped_test_number_fails(self):
    results = {"runId": "run-1", "testCases": [{"testNumber": 99, "status": "PASS"}]}
    self.assertIsNone(self.run_checker(results))

  def test_malformed_results_fail(self):
    with tempfile.TemporaryDirectory() as tmp:
      tmp = Path(tmp)
      bad = tmp / "results.json"
      bad.write_text("{oops")
      catalog = good_catalog()
      _, manifest = conv.convert(catalog, "S")
      map_path = write_json(tmp / "map.json", manifest)
      cat_path = write_json(tmp / "catalog.json", catalog)
      self.assertIsNone(checker.check(bad, map_path, cat_path, "c", "v", ""))


if __name__ == "__main__":
  unittest.main()
