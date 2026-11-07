"""Offline tests for eval metadata resolution. No org needed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import convert_service_scenarios as conv
import resolve_eval_metadata as resolver


PLUGIN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<GenAiPlugin xmlns="http://soap.sforce.com/2006/04/metadata">
  <genAiFunctions><functionName>%s</functionName></genAiFunctions>
</GenAiPlugin>
"""

BUNDLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<GenAiPlannerBundle xmlns="http://soap.sforce.com/2006/04/metadata">
  <localTopics><localActionLinks><functionName>triage_service_case</functionName></localActionLinks></localTopics>
  <localTopicLinks><genAiPluginName>triage_case</genAiPluginName></localTopicLinks>
  <localTopicLinks><genAiPluginName>ambiguous_request</genAiPluginName></localTopicLinks>
  <localTopicLinks><genAiPluginName>off_topic</genAiPluginName></localTopicLinks>
  <localTopicLinks><genAiPluginName>escalation</genAiPluginName></localTopicLinks>
</GenAiPlannerBundle>
"""

BOT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<BotVersion xmlns="http://soap.sforce.com/2006/04/metadata">
  <conversationDefinitionPlanners><genAiPlannerName>Svc</genAiPlannerName></conversationDefinitionPlanners>
</BotVersion>
"""


def good_catalog():
  return {
    "catalog": "service-triage",
    "version": 2,
    "static_thresholds": {"min_scenarios_per_category": 1},
    "live_targets": {"normal_outcome_match": 1.0},
    "scenarios": [
      {"id": "n1", "category": "normal", "input": "Checkout is down",
       "apex_outcome": "SUGGESTED", "apex_priority": "High",
       "apex_queue": "Critical_Response", "agent_expect": "run_triage", "notes": "n"},
      {"id": "a1", "category": "ambiguous", "input": "Help",
       "apex_outcome": "NEEDS_CLARIFICATION", "agent_expect": "clarify", "notes": "n"},
      {"id": "e1", "category": "escalation", "input": "Talk to a human",
       "apex_outcome": "SUGGESTED", "apex_priority": "High",
       "apex_queue": "Critical_Response", "agent_expect": "escalate", "notes": "n"},
    ],
  }


def write_project(tmp, plugins=("triage_case", "ambiguous_request", "escalation"),
                  with_bundle=True, with_bot=True, action="triage_service_case"):
  root = Path(tmp) / "proj"
  for name in plugins:
    path = root / "force-app/main/default/genAiPlugins" / (name + ".genAiPlugin-meta.xml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PLUGIN_XML % action)
  if with_bundle:
    path = root / "force-app/main/default/genAiPlannerBundles/Svc.genAiPlannerBundle-meta.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BUNDLE_XML)
  if with_bot:
    path = root / "force-app/main/default/bots/Svc/v1.botVersion-meta.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BOT_XML)
  return root


def convert_to(tmp, catalog):
  spec, manifest = conv.convert(catalog, "Svc")
  spec_path = Path(tmp) / "spec.yaml"
  map_path = Path(tmp) / "map.json"
  spec_path.write_text(conv.render_yaml(spec))
  map_path.write_text(json.dumps(manifest))
  return spec_path, map_path


class ResolveTest(unittest.TestCase):
  def test_success_exact_match(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp)
      spec_path, map_path = convert_to(tmp, good_catalog())
      out_spec = Path(tmp) / "resolved.yaml"
      report_path = Path(tmp) / "report.json"
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(out_spec),
                            "--report", str(report_path)])
      self.assertEqual(0, code)
      report = json.loads(report_path.read_text())
      self.assertEqual(3, report["cases"])
      self.assertIn("triage_case", report["topics"])
      self.assertIn("triage_service_case", report["actions"])
      self.assertEqual([], report["substitutions"])
      self.assertTrue(any("v1.botVersion" in v for v in report["candidate_versions"]))

  def test_case_insensitive_unique_match_resolves(self):
    catalog = {"catalog": "c", "version": 1, "scenarios": [good_catalog()["scenarios"][0]]}
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, plugins=("Triage_Case",), with_bundle=False, with_bot=False)
      spec_path, map_path = convert_to(tmp, catalog)
      out_spec = Path(tmp) / "resolved.yaml"
      report_path = Path(tmp) / "report.json"
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(out_spec),
                            "--report", str(report_path)])
      self.assertEqual(0, code)
      report = json.loads(report_path.read_text())
      self.assertEqual(1, len(report["substitutions"]))
      self.assertIn("Triage_Case", out_spec.read_text())

  def test_missing_topic_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, plugins=("triage_case", "ambiguous_request"), with_bundle=False)
      spec_path, map_path = convert_to(tmp, good_catalog())
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(Path(tmp) / "o.yaml"),
                            "--report", str(Path(tmp) / "r.json")])
      self.assertEqual(1, code)

  def test_ambiguous_topic_fails(self):
    catalog = {"catalog": "c", "version": 1, "scenarios": [good_catalog()["scenarios"][0]]}
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, plugins=("triage_case",), with_bundle=True, with_bot=False)
      bundle = root / "force-app/main/default/genAiPlannerBundles/Svc.genAiPlannerBundle-meta.xml"
      bundle.write_text(bundle.read_text().replace(
        "</GenAiPlannerBundle>",
        "  <localTopicLinks><genAiPluginName>Triage_Case</genAiPluginName></localTopicLinks>\n</GenAiPlannerBundle>"))
      spec, manifest = conv.convert(catalog, "Svc")
      spec["testCases"][0]["expectedTopic"] = "TRIAGE_CASE"
      spec_path = Path(tmp) / "spec.yaml"
      map_path = Path(tmp) / "map.json"
      spec_path.write_text(conv.render_yaml(spec))
      map_path.write_text(json.dumps(manifest))
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(Path(tmp) / "o.yaml"),
                            "--report", str(Path(tmp) / "r.json")])
      self.assertEqual(1, code)

  def test_missing_action_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, with_bundle=False, action="other_action")
      spec_path, map_path = convert_to(tmp, good_catalog())
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(Path(tmp) / "o.yaml"),
                            "--report", str(Path(tmp) / "r.json")])
      self.assertEqual(1, code)

  def test_no_metadata_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp) / "empty"
      root.mkdir()
      spec_path, map_path = convert_to(tmp, good_catalog())
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(Path(tmp) / "o.yaml"),
                            "--report", str(Path(tmp) / "r.json")])
      self.assertEqual(1, code)

  def test_history_topics_resolve(self):
    catalog = {"catalog": "c", "version": 1, "scenarios": [
      {"id": "f1", "category": "ambiguous", "input": "Checkout is down now",
       "apex_outcome": "SUGGESTED", "apex_priority": "High",
       "apex_queue": "Critical_Response", "agent_expect": "run_triage", "notes": "n",
       "turns": [
         {"role": "user", "message": "Help"},
         {"role": "agent", "message": "What is affected?", "agent_expect": "clarify"},
         {"role": "user", "message": "Checkout is down now"},
       ]},
    ]}
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, plugins=("triage_case", "ambiguous_request"),
                           with_bundle=False, with_bot=False)
      spec_path, map_path = convert_to(tmp, catalog)
      out_spec = Path(tmp) / "resolved.yaml"
      report_path = Path(tmp) / "report.json"
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(out_spec),
                            "--report", str(report_path)])
      self.assertEqual(0, code)
      self.assertIn("ambiguous_request", out_spec.read_text())

  def test_count_mismatch_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp)
      spec_path, map_path = convert_to(tmp, good_catalog())
      manifest = json.loads(map_path.read_text())
      manifest["cases"] = manifest["cases"][:1]
      map_path.write_text(json.dumps(manifest))
      code = resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                            "--project-root", str(root), "--out-spec", str(Path(tmp) / "o.yaml"),
                            "--report", str(Path(tmp) / "r.json")])
      self.assertEqual(1, code)


if __name__ == "__main__":
  unittest.main()
