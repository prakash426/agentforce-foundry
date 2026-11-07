"""Resolve eval spec topics and actions against published org metadata.

Reads a converted test spec plus its mapping manifest, scans the DX
project for GenAiPlugin and GenAiPlannerBundle metadata retrieved by
publish, and resolves every expectedTopic and expectedAction to a real
developer name. Fails before test creation on missing or ambiguous
matches. Writes a resolved spec plus a report tying the spec to the
candidate metadata snapshot. No org needed.

Metadata shapes follow the structures the agent plugin itself parses:
BotVersion carries conversationDefinitionPlanners with a planner name,
GenAiPlannerBundle carries localTopics with action links and
localTopicLinks with plugin names, and GenAiPlugin carries function
names. Files are found by XML root tag, not by filename guess.

Matching is exact first, then case-insensitive when exactly one
candidate matches. Zero matches fail as missing. Multiple
case-insensitive matches fail as ambiguous. The report records every
substitution plus the metadata files and candidate versions seen, so
the resolved spec stays tied to that candidate.

Usage:
  python3 tests/eval/resolve_eval_metadata.py --spec SPEC --map MAP
    --project-root DIR --out-spec OUT --report REPORT
    [--agent NAME]
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def fail(msg):
  print("resolve error: " + msg, file=sys.stderr)
  return None


def local_tag(tag):
  return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child_text(node, name):
  for child in node:
    if local_tag(child.tag) == name and child.text and child.text.strip():
      return child.text.strip()
  return ""


def scan_metadata(root):
  """Return (topics, actions, files, versions) from project metadata."""
  topics, actions, files, versions = {}, {}, [], []
  for path in sorted(root.rglob("*-meta.xml")):
    try:
      tree = ET.parse(str(path))
    except ET.ParseError:
      continue
    tag = local_tag(tree.getroot().tag)
    rel = str(path.relative_to(root))
    if tag == "GenAiPlugin":
      files.append(rel)
      stem = path.name
      if stem.endswith("-meta.xml"):
        stem = stem[: -len("-meta.xml")]
      full_name = stem.rsplit(".", 1)[0] if "." in stem else stem
      if full_name and full_name != "*":
        topics[full_name] = rel
      for node in tree.getroot().iter():
        if local_tag(node.tag) == "functionName" and node.text and node.text.strip():
          actions[node.text.strip()] = rel
    elif tag == "GenAiPlannerBundle":
      files.append(rel)
      for node in tree.getroot().iter():
        ltag = local_tag(node.tag)
        if ltag == "functionName" and node.text and node.text.strip():
          actions[node.text.strip()] = rel
        if ltag == "genAiPluginName" and node.text and node.text.strip():
          topics.setdefault(node.text.strip(), rel)
    elif tag == "BotVersion":
      files.append(rel)
      versions.append(rel)
  return topics, actions, sorted(set(files)), sorted(versions)


def resolve_one(value, candidates, kind, case_ref):
  if value in candidates:
    return value, None
  lowered = value.lower()
  matches = sorted(name for name in candidates if name.lower() == lowered)
  if len(matches) == 1:
    return matches[0], "%s %s resolved %s to %s" % (kind, case_ref, value, matches[0])
  if not matches:
    fail("%s %s has no metadata match for %s; known: %s" % (
      kind, case_ref, value, ", ".join(sorted(candidates)) or "none"))
    return None, None
  fail("%s %s is ambiguous for %s; matches: %s" % (kind, case_ref, value, ", ".join(matches)))
  return None, None


def parse_spec_cases(text):
  """Parse the converter spec back into cases. Only the fields the
  converter writes are read; anything else fails loudly."""
  cases = []
  current = None
  history = None
  for raw in text.splitlines():
    line = raw.rstrip()
    if line.startswith("  - utterance: "):
      current = {"utterance": json.loads(line.split(":", 1)[1].strip()),
                 "expectedActions": [], "conversationHistory": []}
      cases.append(current)
      history = None
    elif current is None:
      continue
    elif line.startswith("    expectedTopic: "):
      current["expectedTopic"] = json.loads(line.split(":", 1)[1].strip())
    elif line.startswith("    expectedOutcome: "):
      current["expectedOutcome"] = json.loads(line.split(":", 1)[1].strip())
    elif line.startswith("    expectedActions: []"):
      current["expectedActions"] = []
    elif line.startswith("      - role: "):
      history = {"role": json.loads(line.split(":", 1)[1].strip())}
      current["conversationHistory"].append(history)
    elif line.startswith("      - ") and history is None:
      current["expectedActions"].append(json.loads(line.strip()[2:]))
    elif line.startswith("    conversationHistory: []"):
      current["conversationHistory"] = []
    elif line.startswith("        message: ") and history is not None:
      history["message"] = json.loads(line.split(":", 1)[1].strip())
    elif line.startswith("        topic: ") and history is not None:
      history["topic"] = json.loads(line.split(":", 1)[1].strip())
  for idx, case in enumerate(cases):
    for field in ("utterance", "expectedTopic", "expectedOutcome"):
      if field not in case:
        return fail("spec case %d lacks %s" % (idx + 1, field))
  return cases


def resolve_project(spec_text, mapping, root):
  topics, actions, files, versions = scan_metadata(Path(root))
  if not topics:
    return fail("no GenAiPlugin topics found under %s; publish must retrieve first" % root)
  if not isinstance(mapping, dict) or not isinstance(mapping.get("cases"), list):
    return fail("mapping manifest has no cases list")
  cases = parse_spec_cases(spec_text)
  if cases is None:
    return None
  if len(cases) != len(mapping["cases"]):
    return fail("spec holds %d cases but mapping holds %d" % (len(cases), len(mapping["cases"])))
  substitutions = []
  for idx, case in enumerate(cases):
    ref = "case %d (%s)" % (idx + 1, mapping["cases"][idx].get("scenario_id"))
    resolved_topic, note = resolve_one(case["expectedTopic"], topics, "topic", ref)
    if resolved_topic is None:
      return None
    case["expectedTopic"] = resolved_topic
    if note:
      substitutions.append(note)
    resolved_actions = []
    for action in case["expectedActions"]:
      resolved_action, note = resolve_one(action, actions, "action", ref)
      if resolved_action is None:
        return None
      resolved_actions.append(resolved_action)
      if note:
        substitutions.append(note)
    case["expectedActions"] = resolved_actions
    for turn in case["conversationHistory"]:
      if "topic" in turn and turn["topic"] not in topics:
        fixed, note = resolve_one(turn["topic"], topics, "history topic", ref)
        if fixed is None:
          return None
        turn["topic"] = fixed
        if note:
          substitutions.append(note)
  report = {
    "kind": "eval-metadata-resolution",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "cases": len(cases),
    "topics": sorted(topics),
    "actions": sorted(actions),
    "metadata_files": files,
    "candidate_versions": versions,
    "substitutions": substitutions,
  }
  return cases, report


def render_yaml(header, cases):
  lines = list(header)
  lines.append("testCases:")
  for case in cases:
    lines.append("  - utterance: " + json.dumps(case["utterance"]))
    lines.append("    expectedTopic: " + json.dumps(case["expectedTopic"]))
    if case["expectedActions"]:
      lines.append("    expectedActions:")
      for action in case["expectedActions"]:
        lines.append("      - " + json.dumps(action))
    else:
      lines.append("    expectedActions: []")
    lines.append("    expectedOutcome: " + json.dumps(case["expectedOutcome"]))
    lines.append("    customEvaluations: []")
    if case["conversationHistory"]:
      lines.append("    conversationHistory:")
      for turn in case["conversationHistory"]:
        lines.append("      - role: " + json.dumps(turn["role"]))
        lines.append("        message: " + json.dumps(turn["message"]))
        if "topic" in turn:
          lines.append("        topic: " + json.dumps(turn["topic"]))
    else:
      lines.append("    conversationHistory: []")
  return "\n".join(lines) + "\n"


def main(argv):
  root = Path(os.environ.get("FOUNDRY_ROOT", str(DEFAULT_ROOT)))
  spec_path = None
  map_path = None
  project_root = root
  out_spec = None
  report_path = None
  args = list(argv)
  while args:
    arg = args.pop(0)
    if arg == "--spec" and args:
      spec_path = Path(args.pop(0))
    elif arg == "--map" and args:
      map_path = Path(args.pop(0))
    elif arg == "--project-root" and args:
      project_root = Path(args.pop(0))
    elif arg == "--out-spec" and args:
      out_spec = Path(args.pop(0))
    elif arg == "--report" and args:
      report_path = Path(args.pop(0))
    elif arg == "--agent" and args:
      args.pop(0)
    else:
      print("resolve error: unknown argument " + arg, file=sys.stderr)
      return 2
  if not spec_path or not map_path or not out_spec or not report_path:
    print("resolve error: --spec, --map, --out-spec, and --report are required", file=sys.stderr)
    return 2
  try:
    spec_text = spec_path.read_text()
    mapping = json.loads(map_path.read_text())
  except Exception as exc:
    print("resolve error: cannot read inputs: %s" % exc, file=sys.stderr)
    return 1
  header = [line for line in spec_text.splitlines()
            if line.startswith(("name:", "description:", "subjectType:", "subjectName:"))]
  result = resolve_project(spec_text, mapping, project_root)
  if result is None:
    return 1
  cases, report = result
  out_spec.parent.mkdir(parents=True, exist_ok=True)
  report_path.parent.mkdir(parents=True, exist_ok=True)
  out_spec.write_text(render_yaml(header, cases))
  report_path.write_text(json.dumps(report, indent=2))
  print(json.dumps({"ok": True, "cases": len(cases),
                    "substitutions": len(report["substitutions"]),
                    "spec": str(out_spec), "report": str(report_path)}, indent=2))
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
