"""Offline static checks for Foundry kits. No org needed.

What this proves: required files exist, the Service catalog parses
against its schema, permission sets reference real classes, and key
source markers are present. It never reimplements Apex logic, so a
pass here is not proof that Apex or any agent behaves correctly.
Apex behavior is covered by Apex tests. Agent behavior needs a
live org run. Exits nonzero when any check fails.
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
KITS = ["service-triage", "sales-qualification", "internal-help"]
SERVICE_SUITE_KEYS = {"catalog", "version", "scenarios", "static_thresholds"}
SCENARIO_KEYS = {"id", "category", "input", "apex_outcome", "agent_expect"}
CATEGORIES = {"normal", "ambiguous", "adversarial", "out_of_scope", "escalation"}
OUTCOMES = {"SUGGESTED", "NEEDS_CLARIFICATION", "NEEDS_REVIEW"}
APEX_MARKERS = {
  "force-app/main/default/classes/ServiceTriageAction.cls": ["@InvocableMethod", "OUTCOME_SUGGESTED"],
  "force-app/main/default/classes/ServiceTriageActionTest.cls": ["@IsTest", "System.assertEquals"],
}
AGENT_DIR = Path("force-app/main/default/aiAuthoringBundles/Service_Triage_Agent")
MD_NS = {"m": "http://soap.sforce.com/2006/04/metadata"}


def check_kit_readmes(root):
  missing = [k for k in KITS if not (root / "kits" / k / "README.md").exists()]
  if missing:
    return ("kit-readmes", False, "missing READMEs: " + ", ".join(missing))
  return ("kit-readmes", True, "all 3 kit READMEs present")


def check_service_catalog(root):
  path = root / "tests" / "testing-center" / "service-triage.json"
  if not path.exists():
    return ("service-catalog", False, "missing tests/testing-center/service-triage.json")
  try:
    data = json.loads(path.read_text())
  except Exception as exc:
    return ("service-catalog", False, "service catalog has invalid JSON: " + str(exc))
  absent = SERVICE_SUITE_KEYS - set(data.keys())
  if absent:
    return ("service-catalog", False, "service catalog missing keys: " + ", ".join(sorted(absent)))
  scenarios = data["scenarios"]
  if not isinstance(scenarios, list) or not scenarios:
    return ("service-catalog", False, "service catalog scenarios must be a nonempty list")
  seen, problems = set(), []
  for idx, case in enumerate(scenarios):
    if not isinstance(case, dict):
      problems.append("scenario index %d is not an object" % idx)
      continue
    absent_keys = SCENARIO_KEYS - set(case.keys())
    if absent_keys:
      problems.append("scenario index %d missing keys: %s" % (idx, ", ".join(sorted(absent_keys))))
      continue
    if case["id"] in seen:
      problems.append("duplicate scenario id: " + str(case["id"]))
    seen.add(case["id"])
    if not str(case["input"]).strip():
      problems.append("scenario %s has blank input" % case["id"])
    if case["category"] not in CATEGORIES:
      problems.append("scenario %s has unknown category" % case["id"])
    if case["apex_outcome"] not in OUTCOMES:
      problems.append("scenario %s has unknown apex_outcome" % case["id"])
    if case["apex_outcome"] == "SUGGESTED" and not (case.get("apex_priority") and case.get("apex_queue")):
      problems.append("scenario %s SUGGESTED without priority and queue" % case["id"])
  if problems:
    return ("service-catalog", False, "; ".join(problems))
  return ("service-catalog", True, "%d scenarios valid" % len(scenarios))


def check_legacy_suites(root):
  missing = [k for k in ("sales-qualification", "internal-help")
             if not (root / "tests" / "testing-center" / (k + ".json")).exists()]
  if missing:
    return ("legacy-suites", False, "missing legacy suites: " + ", ".join(missing))
  return ("legacy-suites", True, "sales and internal suites present (legacy format, presence only)")


def check_apex_markers(root):
  problems = []
  for rel, markers in APEX_MARKERS.items():
    path = root / rel
    if not path.exists():
      problems.append("missing " + rel)
      continue
    text = path.read_text()
    for marker in markers:
      if marker not in text:
        problems.append(rel + " lacks marker " + marker)
  if problems:
    return ("apex-markers", False, "; ".join(problems))
  return ("apex-markers", True, "Service action and test markers present")


def check_permset_refs(root):
  path = root / "force-app/main/default/permissionsets/Agentforce_Foundry_Service.permissionset-meta.xml"
  if not path.exists():
    return ("permset-refs", False, "missing Foundry Service permission set")
  try:
    tree = ET.parse(str(path))
  except Exception as exc:
    return ("permset-refs", False, "permission set XML does not parse: " + str(exc))
  names = [n.text for n in tree.getroot().findall(".//m:apexClass", MD_NS) if n.text]
  if not names:
    return ("permset-refs", False, "permission set grants no Apex classes")
  missing = [n for n in names
             if not (root / "force-app/main/default/classes" / (n + ".cls")).exists()]
  if missing:
    return ("permset-refs", False, "permission set references missing classes: " + ", ".join(missing))
  return ("permset-refs", True, "permission set references resolve: " + ", ".join(names))


def check_agent_bundle(root):
  agent = root / AGENT_DIR / "Service_Triage_Agent.agent"
  meta = root / AGENT_DIR / "Service_Triage_Agent.bundle-meta.xml"
  if not agent.exists():
    return ("agent-bundle", False, "missing Service_Triage_Agent.agent")
  if not meta.exists():
    return ("agent-bundle", False, "missing Service_Triage_Agent.bundle-meta.xml")
  text = agent.read_text()
  for marker in ("apex://ServiceTriageAction", "triage_service_case", "default_agent_user"):
    if marker not in text:
      return ("agent-bundle", False, "agent script lacks marker " + marker)
  if "AGENT" not in meta.read_text():
    return ("agent-bundle", False, "bundle meta does not declare AGENT type")
  return ("agent-bundle", True, "agent script and bundle meta present with action binding")


def run(root=None):
  root = Path(root) if root else DEFAULT_ROOT
  results = [
    check_kit_readmes(root),
    check_service_catalog(root),
    check_legacy_suites(root),
    check_apex_markers(root),
    check_permset_refs(root),
    check_agent_bundle(root),
  ]
  checks = [{"name": n, "ok": ok, "detail": d} for (n, ok, d) in results]
  errors = [c["name"] + ": " + c["detail"] for c in checks if not c["ok"]]
  return {"checks": checks, "ok": not errors, "errors": errors}


if __name__ == "__main__":
  root = Path(os.environ.get("FOUNDRY_ROOT", str(DEFAULT_ROOT)))
  outcome = run(root)
  print(json.dumps(outcome, indent=2))
  sys.exit(0 if outcome["ok"] else 1)
