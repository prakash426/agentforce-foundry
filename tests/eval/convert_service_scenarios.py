"""Convert the committed Service Triage scenario catalog into a test spec.

Reads tests/testing-center/service-triage.json and writes a legacy
testing-center test spec YAML plus a mapping manifest. The YAML uses
only fields verified against the installed Salesforce agent plugin
source (utterance, expectedTopic, expectedActions, expectedOutcome,
customEvaluations, conversationHistory; top level name, description,
subjectType, subjectName, testCases). Multi-turn scenarios become one
test case whose final user turn is the utterance and whose prior turns
become conversationHistory, which is the platform supported multi-turn
path. No org needed. Exits nonzero when the catalog is invalid.

Limitations, stated plainly:
1. expectedTopic uses subagent developer names as initial values. The
   metadata resolver rewrites them against retrieved GenAiPlugin
   developer names before test creation, failing on missing names.
2. expectedActions uses the triage action name for run_triage and an
   empty list otherwise. The resolver verifies each action the same way.
3. expectedOutcome is natural language. The platform cannot assert Apex
   outcome codes directly; Apex codes stay covered by Apex unit tests.
4. customEvaluations ships empty. JSONPath evals need generated data
   from a first verbose run; add them manually afterward.
5. Escalate means a written human follow up recommendation. V1 never
   transfers, so no handoff assertion is emitted.
6. Seeded history tests the next response in context; it does not prove
   the agent produced earlier turns. Use the sequential preview script
   for real multi-turn proof with transcripts.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
CONVERTER_VERSION = "1.0.0"

TOPIC_FOR_EXPECT = {
  "run_triage": "triage_case",
  "clarify": "ambiguous_request",
  "redirect": "off_topic",
  "escalate": "escalation",
}
TRIAGE_ACTION_NAME = "triage_service_case"


def fail(msg):
  print("convert error: " + msg, file=sys.stderr)
  return None


def load_catalog(path):
  try:
    return json.loads(Path(path).read_text())
  except Exception as exc:
    fail("catalog does not parse: " + str(exc))
    return None


def validate(catalog):
  for key in ("catalog", "version", "scenarios"):
    if key not in catalog:
      return fail("catalog missing key: " + key)
  scenarios = catalog["scenarios"]
  if not isinstance(scenarios, list) or not scenarios:
    return fail("scenarios must be a nonempty list")
  seen = set()
  for idx, case in enumerate(scenarios):
    if not isinstance(case, dict):
      return fail("scenario index %d is not an object" % idx)
    for key in ("id", "category", "input", "apex_outcome", "agent_expect"):
      if key not in case:
        return fail("scenario index %d missing key %s" % (idx, key))
    sid = case["id"]
    if sid in seen:
      return fail("duplicate scenario id: " + str(sid))
    seen.add(sid)
    if not str(case["input"]).strip():
      return fail("scenario %s has blank input" % sid)
    if case["apex_outcome"] == "SUGGESTED":
      if not (case.get("apex_priority") and case.get("apex_queue")):
        return fail("scenario %s SUGGESTED without priority and queue" % sid)
    elif case["apex_outcome"] in ("NEEDS_CLARIFICATION", "NEEDS_REVIEW"):
      if case.get("apex_priority") or case.get("apex_queue"):
        return fail("scenario %s %s must not set priority or queue" % (sid, case["apex_outcome"]))
    else:
      return fail("scenario %s has unknown apex_outcome" % sid)
    if case["agent_expect"] not in TOPIC_FOR_EXPECT:
      return fail("scenario %s has unknown agent_expect" % sid)
    turns = case.get("turns")
    if turns is not None:
      ok = validate_turns(sid, turns, case["input"])
      if not ok:
        return None
  return scenarios


def validate_turns(sid, turns, top_input):
  if not isinstance(turns, list) or not turns:
    return fail("scenario %s turns must be a nonempty list" % sid)
  for idx, turn in enumerate(turns):
    if not isinstance(turn, dict):
      return fail("scenario %s turn %d is not an object" % (sid, idx))
    if turn.get("role") not in ("user", "agent"):
      return fail("scenario %s turn %d has unknown role" % (sid, idx))
    if not str(turn.get("message", "")).strip():
      return fail("scenario %s turn %d has blank message" % (sid, idx))
    if "agent_expect" in turn and turn["agent_expect"] not in TOPIC_FOR_EXPECT:
      return fail("scenario %s turn %d has unknown agent_expect" % (sid, idx))
  users = [t for t in turns if t.get("role") == "user"]
  if not users:
    return fail("scenario %s turns have no user turn" % sid)
  if str(users[-1]["message"]).strip() != str(top_input).strip():
    return fail("scenario %s final user turn must equal input" % sid)
  return True


def expected_outcome(case):
  sid = case["id"]
  expect = case["agent_expect"]
  apex = case["apex_outcome"]
  if expect == "run_triage" and apex == "SUGGESTED":
    base = "Agent suggests %s priority for %s." % (case["apex_priority"], case["apex_queue"])
  elif expect == "clarify":
    base = "Agent asks one targeted clarifying question and states no priority or queue."
  elif expect == "redirect":
    base = "Agent redirects to support triage without answering or presenting a triage result."
  elif expect == "escalate":
    base = "Agent recommends human follow up and never claims a transfer happened."
  else:
    base = "Agent responds per the %s behavior." % expect
  notes = str(case.get("notes", "")).strip()
  if notes:
    base += " Context: " + notes
  return base + " Scenario " + sid + "."


def history_for(case):
  turns = case.get("turns") or []
  user_indexes = [i for i, t in enumerate(turns) if t.get("role") == "user"]
  if not user_indexes:
    return []
  final_idx = user_indexes[-1]
  history = []
  for idx, turn in enumerate(turns):
    if idx == final_idx:
      continue
    if turn.get("role") == "user":
      history.append({"role": "user", "message": str(turn["message"])})
    else:
      topic = TOPIC_FOR_EXPECT.get(turn.get("agent_expect", "clarify"), "ambiguous_request")
      history.append({"role": "agent", "message": str(turn["message"]), "topic": topic})
  return history


def qtext(value):
  return json.dumps(str(value))


def render_yaml(spec):
  lines = []
  lines.append("name: " + qtext(spec["name"]))
  lines.append("description: " + qtext(spec["description"]))
  lines.append("subjectType: " + qtext(spec["subjectType"]))
  lines.append("subjectName: " + qtext(spec["subjectName"]))
  lines.append("testCases:")
  for case in spec["testCases"]:
    lines.append("  - utterance: " + qtext(case["utterance"]))
    lines.append("    expectedTopic: " + qtext(case["expectedTopic"]))
    if case["expectedActions"]:
      lines.append("    expectedActions:")
      for action in case["expectedActions"]:
        lines.append("      - " + qtext(action))
    else:
      lines.append("    expectedActions: []")
    lines.append("    expectedOutcome: " + qtext(case["expectedOutcome"]))
    lines.append("    customEvaluations: []")
    if case["conversationHistory"]:
      lines.append("    conversationHistory:")
      for turn in case["conversationHistory"]:
        lines.append("      - role: " + qtext(turn["role"]))
        lines.append("        message: " + qtext(turn["message"]))
        if "topic" in turn:
          lines.append("        topic: " + qtext(turn["topic"]))
    else:
      lines.append("    conversationHistory: []")
  return "\n".join(lines) + "\n"


def convert(catalog, subject_name):
  scenarios = validate(catalog)
  if scenarios is None:
    return None
  cases = []
  mapping = []
  for idx, case in enumerate(scenarios):
    expect = case["agent_expect"]
    topic = TOPIC_FOR_EXPECT[expect]
    if expect == "clarify" and not str(case["input"]).strip():
      topic = "missing_info"
    actions = [TRIAGE_ACTION_NAME] if expect == "run_triage" else []
    cases.append({
      "utterance": str(case["input"]),
      "expectedTopic": topic,
      "expectedActions": actions,
      "expectedOutcome": expected_outcome(case),
      "customEvaluations": [],
      "conversationHistory": history_for(case),
    })
    mapping.append({"index": idx, "testNumber": idx + 1,
                    "scenario_id": case["id"], "category": case.get("category"),
                    "agent_expect": expect, "apex_outcome": case["apex_outcome"]})
  spec = {
    "name": "Service Triage Agent Test",
    "description": "Converted from catalog version %s. Resolve topics and actions against published GenAi metadata before create." % catalog.get("version"),
    "subjectType": "AGENT",
    "subjectName": subject_name,
    "testCases": cases,
  }
  manifest = {
    "kind": "test-spec-mapping",
    "converter_version": CONVERTER_VERSION,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "catalog": catalog.get("catalog"),
    "catalog_version": catalog.get("version"),
    "subjectName": subject_name,
    "cases": mapping,
  }
  return spec, manifest


def main(argv):
  root = Path(os.environ.get("FOUNDRY_ROOT", str(DEFAULT_ROOT)))
  catalog_path = root / "tests" / "testing-center" / "service-triage.json"
  spec_path = root / "specs" / "Service_Triage_Agent-testSpec.yaml"
  map_path = root / "specs" / "Service_Triage_Agent-testMap.json"
  subject_name = "Service_Triage_Agent"
  args = list(argv)
  while args:
    arg = args.pop(0)
    if arg == "--catalog" and args:
      catalog_path = Path(args.pop(0))
    elif arg == "--out-spec" and args:
      spec_path = Path(args.pop(0))
    elif arg == "--out-map" and args:
      map_path = Path(args.pop(0))
    elif arg == "--subject-name" and args:
      subject_name = args.pop(0)
    else:
      print("convert error: unknown argument " + arg, file=sys.stderr)
      return 2
  catalog = load_catalog(catalog_path)
  if catalog is None:
    return 1
  result = convert(catalog, subject_name)
  if result is None:
    return 1
  spec, manifest = result
  spec_path.parent.mkdir(parents=True, exist_ok=True)
  map_path.parent.mkdir(parents=True, exist_ok=True)
  spec_path.write_text(render_yaml(spec))
  map_path.write_text(json.dumps(manifest, indent=2))
  print(json.dumps({"ok": True, "cases": len(spec["testCases"]),
                    "spec": str(spec_path), "map": str(map_path)}, indent=2))
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
