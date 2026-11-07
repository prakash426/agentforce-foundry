"""Offline tests for candidate-scoped metadata resolution. No org needed."""
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
%s
</GenAiPlannerBundle>
"""

BOT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<BotVersion xmlns="http://soap.sforce.com/2006/04/metadata">
  <conversationDefinitionPlanners><genAiPlannerName>%s</genAiPlannerName></conversationDefinitionPlanners>
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
    ],
  }


def bundle_body(topics, actions=()):
  parts = [("<localTopicLinks><genAiPluginName>%s</genAiPluginName></localTopicLinks>" % t)
           for t in topics]
  links = "".join("<localActionLinks><functionName>%s</functionName></localActionLinks>" % a
                  for a in actions)
  parts.append("<localTopics>" + links + "</localTopics>")
  return BUNDLE_XML % "\n  ".join(parts)


def write_project(tmp, layout):
  """layout: dict with bots {agent: {version: planner}}, bundles {name: (topics, actions)},
  plugins {name: action}, plus optional raw files {relpath: content}."""
  root = Path(tmp) / "proj"
  for agent, versions in layout.get("bots", {}).items():
    for version, planner in versions.items():
      path = root / "force-app/main/default/bots" / agent / ("v%s.botVersion-meta.xml" % version)
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(BOT_XML % planner)
  for name, (topics, actions) in layout.get("bundles", {}).items():
    path = root / "force-app/main/default/genAiPlannerBundles" / (name + ".genAiPlannerBundle-meta.xml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bundle_body(topics, actions))
  for name, action in layout.get("plugins", {}).items():
    path = root / "force-app/main/default/genAiPlugins" / (name + ".genAiPlugin-meta.xml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PLUGIN_XML % action)
  for rel, content in layout.get("raw", {}).items():
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
  return root


def standard_layout():
  return {
    "bots": {"SvcA": {"1": "PlannerA1", "2": "PlannerA2"}, "SvcB": {"1": "PlannerB1"}},
    "bundles": {
      "PlannerA1": (["legacy_triage"], ["legacy_action"]),
      "PlannerA2": (["triage_case", "ambiguous_request"], ["triage_service_case"]),
      "PlannerB1": (["billing_case"], ["billing_action"]),
    },
    "plugins": {
      "triage_case": "triage_service_case",
      "ambiguous_request": "triage_service_case",
      "legacy_triage": "legacy_action",
      "billing_case": "billing_action",
      "stale_topic": "stale_action",
    },
  }


def convert_to(tmp, catalog, subject="SvcA"):
  spec, manifest = conv.convert(catalog, subject)
  spec_path = Path(tmp) / "spec.yaml"
  map_path = Path(tmp) / "map.json"
  spec_path.write_text(conv.render_yaml(spec))
  map_path.write_text(json.dumps(manifest))
  return spec_path, map_path


def run_resolve(tmp, root, spec_path, map_path, agent="SvcA", version="2"):
  return resolver.main(["--spec", str(spec_path), "--map", str(map_path),
                        "--agent", agent, "--version", version,
                        "--project-root", str(root),
                        "--out-spec", str(Path(tmp) / "resolved.yaml"),
                        "--report", str(Path(tmp) / "report.json")])


class CandidateScopeTest(unittest.TestCase):
  def test_valid_candidate_resolution(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, standard_layout())
      spec_path, map_path = convert_to(tmp, good_catalog())
      self.assertEqual(0, run_resolve(tmp, root, spec_path, map_path))
      report = json.loads((Path(tmp) / "report.json").read_text())
      self.assertEqual("SvcA", report["agent"])
      self.assertEqual("v2", report["version"])
      self.assertEqual("PlannerA2", report["planner"])
      self.assertIn("triage_case", report["reachable_topics"])
      self.assertIn("triage_service_case", report["reachable_actions"])
      self.assertNotIn("billing_case", report["reachable_topics"])
      self.assertEqual(2, len(report["decisions"]))
      self.assertTrue(report["decisions"][0]["topicSource"].endswith("triage_case.genAiPlugin-meta.xml"))

  def test_other_agent_name_rejected(self):
    catalog = good_catalog()
    catalog["scenarios"][1]["agent_expect"] = "escalate"
    catalog["scenarios"][1]["apex_outcome"] = "SUGGESTED"
    catalog["scenarios"][1]["apex_priority"] = "High"
    catalog["scenarios"][1]["apex_queue"] = "Critical_Response"
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, standard_layout())
      spec, manifest = conv.convert(catalog, "SvcA")
      spec["testCases"][1]["expectedTopic"] = "billing_case"
      spec_path = Path(tmp) / "spec.yaml"
      map_path = Path(tmp) / "map.json"
      spec_path.write_text(conv.render_yaml(spec))
      map_path.write_text(json.dumps(manifest))
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path))

  def test_other_version_action_rejected(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, standard_layout())
      spec, manifest = conv.convert(good_catalog(), "SvcA")
      spec["testCases"][0]["expectedTopic"] = "legacy_triage"
      spec_path = Path(tmp) / "spec.yaml"
      map_path = Path(tmp) / "map.json"
      spec_path.write_text(conv.render_yaml(spec))
      map_path.write_text(json.dumps(manifest))
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path, version="1"))

  def test_stale_topic_rejected(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, standard_layout())
      spec, manifest = conv.convert(good_catalog(), "SvcA")
      spec["testCases"][0]["expectedTopic"] = "stale_topic"
      spec_path = Path(tmp) / "spec.yaml"
      map_path = Path(tmp) / "map.json"
      spec_path.write_text(conv.render_yaml(spec))
      map_path.write_text(json.dumps(manifest))
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path))

  def test_stale_action_rejected(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, standard_layout())
      spec, manifest = conv.convert(good_catalog(), "SvcA")
      spec["testCases"][0]["expectedActions"] = ["stale_action"]
      spec_path = Path(tmp) / "spec.yaml"
      map_path = Path(tmp) / "map.json"
      spec_path.write_text(conv.render_yaml(spec))
      map_path.write_text(json.dumps(manifest))
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path))

  def test_missing_version_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, standard_layout())
      spec_path, map_path = convert_to(tmp, good_catalog())
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path, version="9"))

  def test_missing_planner_fails(self):
    layout = standard_layout()
    layout["bots"]["SvcA"]["2"] = "GhostPlanner"
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, layout)
      spec_path, map_path = convert_to(tmp, good_catalog())
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path))

  def test_dangling_topic_fails(self):
    layout = standard_layout()
    layout["bundles"]["PlannerA2"] = (["triage_case", "ghost_topic"], ["triage_service_case"])
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, layout)
      spec_path, map_path = convert_to(tmp, good_catalog())
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path))

  def test_ambiguous_plugin_fails(self):
    layout = standard_layout()
    layout["raw"] = {"force-app/extra/genAiPlugins/triage_case.genAiPlugin-meta.xml":
                     PLUGIN_XML % "triage_service_case"}
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, layout)
      spec_path, map_path = convert_to(tmp, good_catalog())
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path))

  def test_identity_mismatch_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, standard_layout())
      spec_path, map_path = convert_to(tmp, good_catalog(), subject="SvcB")
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path, agent="SvcA"))

  def test_malformed_bot_version_fails(self):
    layout = standard_layout()
    layout["raw"] = {"force-app/main/default/bots/SvcA/v2.botVersion-meta.xml": "<BotVersion><oops"}
    with tempfile.TemporaryDirectory() as tmp:
      root = write_project(tmp, layout)
      spec_path, map_path = convert_to(tmp, good_catalog())
      self.assertEqual(1, run_resolve(tmp, root, spec_path, map_path))

  def test_history_topics_use_candidate(self):
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
      root = write_project(tmp, standard_layout())
      spec_path, map_path = convert_to(tmp, catalog)
      self.assertEqual(0, run_resolve(tmp, root, spec_path, map_path))
      self.assertIn("ambiguous_request", (Path(tmp) / "resolved.yaml").read_text())


if __name__ == "__main__":
  unittest.main()
