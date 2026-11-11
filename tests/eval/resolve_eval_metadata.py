"""Resolve eval spec topics and actions against one candidate version.

Reads a converted test spec plus its mapping manifest, follows the
selected candidate version to exactly the topics and actions
reachable from that candidate, and resolves every expected name
within that reachable set only. Names that exist solely in another
agent or version are rejected, never silently borrowed. Fails before
test creation on missing, ambiguous, malformed, or dangling
references. Writes a resolved spec plus a report recording the
candidate, every traversed reference, and each decision. No org needed.

Two retrieval layouts are supported, because publish retrieval has
been observed in both shapes and the layout is not attributed to any
API version without evidence:

- Legacy: bots/<Agent>/v<N>.botVersion-meta.xml names its planner
  through conversationDefinitionPlanners, a GenAiPlannerBundle links
  topics through localTopicLinks and actions through localTopics
  action links, and each GenAiPlugin names its functions.
- Current: aiAgentDefinitionVersions/<Agent>#<N>/
  <Agent>#<N>.aiAgentDefinitionVersion-meta.xml carries an inline
  planner with localTopicLinks, localTopics, localActionLinks, and
  localActions, plus a version element that must match.

Metadata full names come from file names, the same way the platform
derives them. No project-wide name search is used for resolution; the
full project is consulted only to explain where an outside-candidate
name lives.

Usage:
  python3 tests/eval/resolve_eval_metadata.py --spec SPEC --map MAP
    --agent NAME --version N --project-root DIR --out-spec OUT
    --report REPORT
"""
import json
import os
import re
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


def full_name_of(path):
  stem = path.name
  if stem.endswith("-meta.xml"):
    stem = stem[: -len("-meta.xml")]
  return stem.split(".", 1)[0] if "." in stem else stem


def version_of_bot_file(path):
  match = re.match(r"v(\d+)\b", path.name)
  return match.group(1) if match else ""


def parse_xml(path):
  try:
    return ET.parse(str(path)).getroot()
  except ET.ParseError as exc:
    fail("metadata file %s does not parse: %s" % (path, exc))
    return None


def find_bot_version(root, agent, version):
  matches = []
  for path in sorted(root.rglob("*-meta.xml")):
    if path.parent.name != agent:
      continue
    if version_of_bot_file(path) != version:
      continue
    try:
      tree = ET.parse(str(path))
    except ET.ParseError:
      return fail("candidate file %s does not parse" % path.relative_to(root))
    if local_tag(tree.getroot().tag) != "BotVersion":
      continue
    matches.append(path)
  if len(matches) > 1:
    fail("ambiguous BotVersion files for agent %s version v%s" % (agent, version))
    return None
  return matches[0] if matches else None


def find_agent_definition_version(root, agent, version):
  matches = []
  wanted_dir = "%s#%s" % (agent, version)
  for path in sorted(root.rglob("*-meta.xml")):
    if path.parent.name != wanted_dir:
      continue
    try:
      parsed = ET.parse(str(path)).getroot()
    except ET.ParseError:
      fail("candidate file %s does not parse" % path.relative_to(root))
      return None
    if local_tag(parsed.tag) != "AiAgentDefinitionVersion":
      continue
    file_version = ""
    for node in parsed.iter():
      if local_tag(node.tag) == "version" and node.text and node.text.strip():
        file_version = node.text.strip()
        break
    if file_version != version:
      fail("candidate file %s declares version %s, expected %s" % (
        path.relative_to(root), file_version or "missing", version))
      return None
    matches.append(path)
  if len(matches) > 1:
    fail("ambiguous AiAgentDefinitionVersion files for agent %s version v%s" % (agent, version))
    return None
  return matches[0] if matches else None


def planner_of(bot_root):
  for planners in bot_root.iter():
    if local_tag(planners.tag) != "conversationDefinitionPlanners":
      continue
    for child in planners:
      if local_tag(child.tag) == "genAiPlannerName" and child.text and child.text.strip():
        return child.text.strip()
  return ""


def find_by_full_name(root, tag, name):
  matches = []
  for path in sorted(root.rglob("*-meta.xml")):
    if full_name_of(path) != name:
      continue
    try:
      parsed = ET.parse(str(path)).getroot()
    except ET.ParseError:
      continue
    if local_tag(parsed.tag) == tag:
      matches.append(path)
  return matches


def collect_planner_refs(planner_root):
  topics = []
  for node in planner_root.iter():
    if local_tag(node.tag) == "genAiPluginName" and node.text and node.text.strip():
      topics.append(node.text.strip())
  actions = []
  for node in planner_root.iter():
    if local_tag(node.tag) == "functionName" and node.text and node.text.strip():
      actions.append(node.text.strip())
  return topics, actions


def collect_inline_refs(version_root):
  topics = []
  for node in version_root.iter():
    if local_tag(node.tag) == "genAiPluginName" and node.text and node.text.strip():
      name = node.text.strip()
      if name not in topics:
        topics.append(name)
  actions = []
  for topic_node in version_root.iter():
    if local_tag(topic_node.tag) != "localTopics":
      continue
    for elem in list(topic_node):
      if local_tag(elem.tag) == "localDeveloperName" and elem.text and elem.text.strip():
        name = elem.text.strip()
        if name not in topics:
          topics.append(name)
      if local_tag(elem.tag) == "localActionLinks":
        for fn in elem.iter():
          if local_tag(fn.tag) == "functionName" and fn.text and fn.text.strip():
            name = fn.text.strip()
            if name not in actions:
              actions.append(name)
      if local_tag(elem.tag) == "localActions":
        for sub in elem.iter():
          if local_tag(sub.tag) == "localDeveloperName" and sub.text and sub.text.strip():
            name = sub.text.strip()
            if name not in actions:
              actions.append(name)
  topics = [t for t in topics if t not in actions]
  return topics, actions


def plugin_functions(plugin_root):
  return [node.text.strip() for node in plugin_root.iter()
          if local_tag(node.tag) == "functionName" and node.text and node.text.strip()]


def project_names(root, tag):
  names = set()
  for path in root.rglob("*-meta.xml"):
    if full_name_of(path) == "*":
      continue
    try:
      parsed = ET.parse(str(path)).getroot()
    except ET.ParseError:
      continue
    if local_tag(parsed.tag) == tag:
      names.add(full_name_of(path))
  return names


def resolve_one(value, reachable, kind, case_ref, agent, version, elsewhere):
  """Resolve within the reachable map of name to source file."""
  if value in reachable:
    return value, reachable[value], None
  lowered = value.lower()
  matches = sorted(name for name in reachable if name.lower() == lowered)
  if len(matches) == 1:
    return matches[0], reachable[matches[0]], "%s %s resolved %s to %s" % (kind, case_ref, value, matches[0])
  if len(matches) > 1:
    fail("%s %s is ambiguous for %s within %s v%s; matches: %s" % (
      kind, case_ref, value, agent, version, ", ".join(matches)))
    return None, None, None
  if value in elsewhere or any(name.lower() == lowered for name in elsewhere):
    fail("%s %s names %s, which exists only outside candidate %s v%s" % (
      kind, case_ref, value, agent, version))
  else:
    fail("%s %s has no metadata match for %s in candidate %s v%s" % (
      kind, case_ref, value, agent, version))
  return None, None, None


def parse_spec_cases(text):
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


def normalize_version(value):
  text = str(value).strip()
  if text.startswith("v"):
    text = text[1:]
  return text if text.isdigit() else ""


def resolve_candidate(spec_text, mapping, root, agent, version):
  if not agent:
    return fail("agent identity is required")
  version = normalize_version(version)
  if not version:
    return fail("candidate version is required (for example 2 or v2)")
  if not isinstance(mapping, dict) or not isinstance(mapping.get("cases"), list):
    return fail("mapping manifest has no cases list")
  if mapping.get("subjectName") != agent:
    return fail("mapping subject %s does not match selected agent %s" % (
      mapping.get("subjectName"), agent))
  root = Path(root)
  layout = ""
  candidate_file = None
  planner = ""
  bundle_file = None
  plugin_files = []
  reachable_topics = {}
  reachable_actions = {}
  bot_file = find_bot_version(root, agent, version)
  version_file = None if bot_file is not None else find_agent_definition_version(root, agent, version)
  if bot_file is None and version_file is None:
    return fail("no candidate metadata for agent %s version v%s: checked bots/%s/v%s and aiAgentDefinitionVersions/%s#%s" % (
      agent, version, agent, version, agent, version))
  if bot_file is not None:
    layout = "legacy-bot"
    candidate_file = bot_file
    bot_root = parse_xml(bot_file)
    if bot_root is None:
      return None
    planner = planner_of(bot_root)
    if not planner:
      return fail("BotVersion %s names no planner" % bot_file.relative_to(root))
    bundles = find_by_full_name(root, "GenAiPlannerBundle", planner)
    if not bundles:
      return fail("planner %s referenced by %s v%s has no bundle file" % (planner, agent, version))
    if len(bundles) > 1:
      return fail("planner %s matches multiple bundle files" % planner)
    bundle_file = bundles[0]
    bundle_root = parse_xml(bundle_file)
    if bundle_root is None:
      return None
    topic_refs, planner_actions = collect_planner_refs(bundle_root)
    for ref in topic_refs:
      plugins = find_by_full_name(root, "GenAiPlugin", ref)
      if not plugins:
        return fail("topic %s referenced by planner %s has no plugin file" % (ref, planner))
      if len(plugins) > 1:
        return fail("topic %s matches multiple plugin files" % ref)
      rel = str(plugins[0].relative_to(root))
      reachable_topics[ref] = rel
      plugin_files.append(rel)
      plugin_root = parse_xml(plugins[0])
      if plugin_root is None:
        return None
    for action in planner_actions:
      reachable_actions.setdefault(action, str(bundle_file.relative_to(root)))
    for ref, rel in sorted(reachable_topics.items()):
      plugin_root = parse_xml(root / rel)
      if plugin_root is None:
        return None
      for action in plugin_functions(plugin_root):
        reachable_actions.setdefault(action, rel)
  else:
    layout = "agent-definition-version"
    candidate_file = version_file
    version_root = parse_xml(version_file)
    if version_root is None:
      return None
    for node in version_root.iter():
      if local_tag(node.tag) == "genAiPlannerName" and node.text and node.text.strip():
        planner = node.text.strip()
        break
    if not planner:
      return fail("candidate %s names no planner" % version_file.relative_to(root))
    topic_refs, inline_actions = collect_inline_refs(version_root)
    rel = str(version_file.relative_to(root))
    for ref in topic_refs:
      reachable_topics[ref] = rel
    for action in inline_actions:
      reachable_actions.setdefault(action, rel)
    plugin_files = []
  elsewhere_topics = project_names(root, "GenAiPlugin") - set(reachable_topics)
  cases = parse_spec_cases(spec_text)
  if cases is None:
    return None
  if len(cases) != len(mapping["cases"]):
    return fail("spec holds %d cases but mapping holds %d" % (len(cases), len(mapping["cases"])))
  elsewhere_actions = set()
  for path in root.rglob("*-meta.xml"):
    try:
      parsed = ET.parse(str(path)).getroot()
    except ET.ParseError:
      continue
    if local_tag(parsed.tag) in ("GenAiPlugin", "GenAiPlannerBundle", "AiAgentDefinitionVersion"):
      for node in parsed.iter():
        if local_tag(node.tag) == "functionName" and node.text and node.text.strip():
          elsewhere_actions.add(node.text.strip())
  elsewhere_actions -= set(reachable_actions)
  decisions = []
  substitutions = []
  for idx, case in enumerate(cases):
    ref = "case %d (%s)" % (idx + 1, mapping["cases"][idx].get("scenario_id"))
    topic, topic_source, note = resolve_one(
      case["expectedTopic"], reachable_topics, "topic", ref, agent, version, elsewhere_topics)
    if topic is None:
      return None
    case["expectedTopic"] = topic
    if note:
      substitutions.append(note)
    action_sources = []
    resolved_actions = []
    for action in case["expectedActions"]:
      fixed, source, note = resolve_one(
        action, reachable_actions, "action", ref, agent, version, elsewhere_actions)
      if fixed is None:
        return None
      resolved_actions.append(fixed)
      action_sources.append(source)
      if note:
        substitutions.append(note)
    case["expectedActions"] = resolved_actions
    for turn in case["conversationHistory"]:
      if "topic" in turn:
        fixed, _, note = resolve_one(
          turn["topic"], reachable_topics, "history topic", ref, agent, version, elsewhere_topics)
        if fixed is None:
          return None
        turn["topic"] = fixed
        if note:
          substitutions.append(note)
    decisions.append({"testNumber": idx + 1, "scenario_id": mapping["cases"][idx].get("scenario_id"),
                      "expectedTopic": topic, "topicSource": topic_source,
                      "expectedActions": resolved_actions, "actionSources": action_sources})
  report = {
    "kind": "eval-metadata-resolution",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "agent": agent,
    "version": "v" + version,
    "layout": layout,
    "planner": planner,
    "candidate_file": str(candidate_file.relative_to(root)),
    "planner_file": str(bundle_file.relative_to(root)) if bundle_file is not None else str(candidate_file.relative_to(root)),
    "plugin_files": sorted(set(plugin_files)),
    "reachable_topics": sorted(reachable_topics),
    "reachable_actions": sorted(reachable_actions),
    "cases": len(cases),
    "decisions": decisions,
    "substitutions": substitutions,
  }
  if layout == "legacy-bot":
    report["bot_version_file"] = str(candidate_file.relative_to(root))
  else:
    report["version_file"] = str(candidate_file.relative_to(root))
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
  agent = ""
  version = ""
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
      agent = args.pop(0)
    elif arg == "--version" and args:
      version = args.pop(0)
    else:
      print("resolve error: unknown argument " + arg, file=sys.stderr)
      return 2
  if not spec_path or not map_path or not out_spec or not report_path:
    print("resolve error: --spec, --map, --out-spec, and --report are required", file=sys.stderr)
    return 2
  if not agent or not version:
    print("resolve error: --agent and --version are required", file=sys.stderr)
    return 2
  try:
    spec_text = spec_path.read_text()
    mapping = json.loads(map_path.read_text())
  except Exception as exc:
    print("resolve error: cannot read inputs: %s" % exc, file=sys.stderr)
    return 1
  header = [line for line in spec_text.splitlines()
            if line.startswith(("name:", "description:", "subjectType:", "subjectName:"))]
  result = resolve_candidate(spec_text, mapping, project_root, agent, version)
  if result is None:
    return 1
  cases, report = result
  out_spec.parent.mkdir(parents=True, exist_ok=True)
  report_path.parent.mkdir(parents=True, exist_ok=True)
  out_spec.write_text(render_yaml(header, cases))
  report_path.write_text(json.dumps(report, indent=2))
  print(json.dumps({"ok": True, "agent": agent, "version": report["version"],
                    "cases": len(cases), "substitutions": len(report["substitutions"]),
                    "spec": str(out_spec), "report": str(report_path)}, indent=2))
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
