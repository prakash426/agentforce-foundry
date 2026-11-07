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
AGENT_EXPECTS = {"run_triage", "clarify", "redirect", "escalate"}
TURN_ROLES = {"user", "agent"}
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
    if case["apex_outcome"] in ("NEEDS_CLARIFICATION", "NEEDS_REVIEW"):
      if case.get("apex_priority") or case.get("apex_queue"):
        problems.append("scenario %s %s must not set priority or queue" % (case["id"], case["apex_outcome"]))
    if case.get("agent_expect") not in AGENT_EXPECTS:
      problems.append("scenario %s has unknown agent_expect" % case["id"])
    turns = case.get("turns")
    if turns is not None:
      problems.extend(check_turns(case["id"], turns, case.get("input")))
  if problems:
    return ("service-catalog", False, "; ".join(problems))
  return ("service-catalog", True, "%d scenarios valid" % len(scenarios))


def check_turns(sid, turns, top_input):
  problems = []
  if not isinstance(turns, list) or not turns:
    return ["scenario %s turns must be a nonempty list" % sid]
  for idx, turn in enumerate(turns):
    if not isinstance(turn, dict):
      problems.append("scenario %s turn %d is not an object" % (sid, idx))
      continue
    if turn.get("role") not in TURN_ROLES:
      problems.append("scenario %s turn %d has unknown role" % (sid, idx))
    if not str(turn.get("message", "")).strip():
      problems.append("scenario %s turn %d has blank message" % (sid, idx))
    if "agent_expect" in turn and turn["agent_expect"] not in AGENT_EXPECTS:
      problems.append("scenario %s turn %d has unknown agent_expect" % (sid, idx))
  users = [t for t in turns if isinstance(t, dict) and t.get("role") == "user"]
  if not users:
    problems.append("scenario %s turns have no user turn" % sid)
  elif str(users[-1].get("message", "")).strip() != str(top_input or "").strip():
    problems.append("scenario %s final user turn must equal input" % sid)
  return problems


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
  for marker in ("back_to_triage", "go_to_escalation", "go_to_off_topic",
                 "@utils.transition to @subagent.triage_case",
                 "@utils.transition to @subagent.escalation",
                 "@utils.transition to @subagent.off_topic"):
    if marker not in text:
      return ("agent-bundle", False, "agent script lacks transition marker " + marker)
  if "@utils.escalate" in text:
    return ("agent-bundle", False, "agent script uses unsupported @utils.escalate without a messaging connection")
  for ref in ("{!@actions.back_to_triage}", "{!@actions.go_to_escalation}", "{!@actions.go_to_off_topic}"):
    if ref not in text:
      return ("agent-bundle", False, "agent script never references transition " + ref)
  if "AGENT" not in meta.read_text():
    return ("agent-bundle", False, "bundle meta does not declare AGENT type")
  return ("agent-bundle", True, "agent script and bundle meta present with action binding and transitions")


SHELL_SCRIPTS = [
  "scripts/setup-service-triage.sh",
  "scripts/setup.sh",
  "scripts/create-service-triage-test.sh",
  "scripts/preview-service-triage-turns.sh",
  "scripts/setup-agent-user.sh",
]
DOC_FILES = [
  "README.md",
  "docs/ARCHITECTURE.md",
  "docs/TESTING.md",
  "docs/EVIDENCE.md",
  "kits/service-triage/README.md",
  "kits/sales-qualification/README.md",
  "kits/internal-help/README.md",
]


def check_shell_scripts(root):
  problems = []
  for rel in SHELL_SCRIPTS:
    path = root / rel
    if not path.exists():
      problems.append("missing " + rel)
      continue
    text = path.read_text()
    first = text.splitlines()[0] if text.splitlines() else ""
    if "bash" not in first:
      problems.append(rel + " must declare a bash shebang for pipefail support")
    if "pipefail" not in text:
      problems.append(rel + " must enable pipefail")
    if "| tee" in text:
      problems.append(rel + " must not pipe into tee without status handling")
    if "verify_step" not in text:
      problems.append(rel + " must verify Salesforce output payloads")
    if "sf_steps.sh" not in text:
      problems.append(rel + " must source the shared step helper")
  lib = root / "scripts" / "lib" / "sf_steps.sh"
  if not lib.exists():
    problems.append("missing scripts/lib/sf_steps.sh")
  elif "verify_sf_output.py" not in lib.read_text():
    problems.append("shared step helper must call the output verifier")
  if not (root / "scripts" / "verify_sf_output.py").exists():
    problems.append("missing scripts/verify_sf_output.py")
  if problems:
    return ("shell-scripts", False, "; ".join(problems))
  return ("shell-scripts", True, "%d org scripts use bash with verified steps" % len(SHELL_SCRIPTS))


def check_docs_consistency(root):
  problems = []
  for rel in DOC_FILES:
    path = root / rel
    if not path.exists():
      continue
    text = path.read_text()
    if "sh scripts/" in text.replace("bash scripts/", ""):
      problems.append(rel + " still invokes scripts with sh instead of bash")
  import re
  refs = set()
  for rel in DOC_FILES:
    path = root / rel
    if not path.exists():
      continue
    for match in re.findall(r"(?:scripts|tests|force-app|manifests|config|specs)/[A-Za-z0-9_./-]+\.(?:sh|py|json|xml|cls|agent|yaml|md)", path.read_text()):
      refs.add(match.rstrip(".,)"))
  for ref in sorted(refs):
    if ref.startswith(("specs/", "tests/eval/results/")):
      continue
    if not (root / ref).exists():
      problems.append("docs reference missing path " + ref)
  if problems:
    return ("docs-consistency", False, "; ".join(problems))
  return ("docs-consistency", True, "docs invoke bash and reference %d real paths" % len(refs))


def run(root=None):
  root = Path(root) if root else DEFAULT_ROOT
  results = [
    check_kit_readmes(root),
    check_service_catalog(root),
    check_legacy_suites(root),
    check_apex_markers(root),
    check_permset_refs(root),
    check_agent_bundle(root),
    check_shell_scripts(root),
    check_docs_consistency(root),
  ]
  checks = [{"name": n, "ok": ok, "detail": d} for (n, ok, d) in results]
  errors = [c["name"] + ": " + c["detail"] for c in checks if not c["ok"]]
  return {"checks": checks, "ok": not errors, "errors": errors}


if __name__ == "__main__":
  root = Path(os.environ.get("FOUNDRY_ROOT", str(DEFAULT_ROOT)))
  outcome = run(root)
  print(json.dumps(outcome, indent=2))
  sys.exit(0 if outcome["ok"] else 1)
