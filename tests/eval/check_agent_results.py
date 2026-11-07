"""Parse agent test run results and enforce acceptance thresholds.

Reads the JSON produced by sf agent test run with result-format json
for the legacy testing-center runner, joins it to the converter mapping
manifest and the committed catalog, and writes a machine-readable
evaluation record. Fails (exit nonzero) when any required case errors,
fails, or is unfinished, when coverage is incomplete, when mapping or
catalog consistency breaks, or when a threshold misses. No org needed.
Static audit, Apex unit tests, and live agent evaluations stay
separate: this script only scores a live run, never the static catalog.

Result shape, verified against the installed @salesforce/agents
sources (types AgentTestResultsResponse and TestCaseResult):
  top level carries status, subjectName, startTime, endTime, and a
  testCases list. Each case carries testNumber, an execution status,
  inputs, generatedData, and a testResults list of per-expectation
  verdicts with name, result (PASS, FAILURE, or null when unfinished),
  status, score, actual and expected values, and error detail. The CLI
  writes this payload to test-result-<runId>.json and prints runId on
  stdout with --json. Verdicts come from the per-expectation results,
  never from a generic execution status.

Inputs:
  --results PATH   results JSON file, or a directory holding JSON files
  --map PATH       converter mapping manifest (testMap.json)
  --catalog PATH   committed scenario catalog (service-triage.json)
  --commit SHA     checked out source commit that was tested
  --pr-head SHA    pull request head commit, when CI tested a merge commit
  --agent-version  candidate agent version activated for the run
  --resolve-report PATH to the resolver report; when given, its agent
                   and version must match the evaluated candidate
  --run-id ID      run identifier captured from CLI stdout (verified
                   against the result filename when both exist)
  --out PATH       evaluation record output (default
                   tests/eval/results/service-triage-eval.json)

Thresholds come from the catalog live_targets block:
  normal_outcome_match is the minimum pass fraction across normal cases.
  ambiguous_never_confident_high, adversarial_never_obeyed, and
  escalation_inputs_reach_human_path each require every case in that
  category to pass, because the spec encodes the expected topic and
  actions per case.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

TERMINAL_OK = "COMPLETED"
TOPIC_NAMES = ("topic_sequence_match", "topic_assertion")
ACTION_NAMES = ("action_sequence_match", "actions_assertion")
OUTCOME_NAMES = ("bot_response_rating", "output_validation")
REQUIRED_GROUPS = (("topic", TOPIC_NAMES), ("actions", ACTION_NAMES), ("outcome", OUTCOME_NAMES))
RUN_FILE_RE = re.compile(r"^test-result-(.+)\.json$")

ERRORS = []


def fail(msg):
  ERRORS.append(msg)
  print("check error: " + msg, file=sys.stderr)
  return None


def load_json(path):
  try:
    return json.loads(Path(path).read_text())
  except Exception as exc:
    fail("cannot parse JSON at %s: %s" % (path, exc))
    return None


def find_results_file(path):
  path = Path(path)
  if path.is_file():
    return path
  if path.is_dir():
    cands = sorted(path.glob("test-result-*.json"))
    if not cands:
      cands = sorted(path.glob("*.json"))
    if len(cands) == 1:
      return cands[0]
    fail("results dir %s must hold exactly one results JSON file, found %d" % (path, len(cands)))
    return None
  fail("results path missing: " + str(path))
  return None


def run_id_from_filename(path):
  match = RUN_FILE_RE.match(Path(path).name)
  return match.group(1) if match else ""


def expectation_verdict(entry):
  """Score one per-expectation entry. Returns (ok, note)."""
  if not isinstance(entry, dict):
    return False, "malformed expectation entry"
  result = entry.get("result")
  status = str(entry.get("status", "")).upper()
  name = str(entry.get("name", "unknown"))
  if status != TERMINAL_OK:
    return False, "%s unfinished with status %s" % (name, status or "missing")
  if result == "PASS":
    return True, ""
  if result == "FAILURE":
    detail = str(entry.get("errorMessage", "") or "assertion failed")[:200]
    return False, "%s failed: %s" % (name, detail)
  return False, "%s has no verdict (result null)" % name


def case_verdict(test_case):
  """Score one legacy test case. Returns (status, notes, expectations)."""
  status = str(test_case.get("status", "")).upper()
  test_results = test_case.get("testResults")
  if status == "ERROR":
    return "ERROR", ["case execution status ERROR"], []
  if status != TERMINAL_OK:
    return "UNFINISHED", ["case execution status %s" % (status or "missing")], []
  if not isinstance(test_results, list) or not test_results:
    return "MALFORMED", ["case has no per-expectation results"], []
  groups_found = {group: [] for group, _ in REQUIRED_GROUPS}
  notes = []
  expectations = []
  all_ok = True
  for entry in test_results:
    ok, note = expectation_verdict(entry)
    name = entry.get("name", "unknown") if isinstance(entry, dict) else "unknown"
    for group, names in REQUIRED_GROUPS:
      if name in names:
        groups_found[group].append(ok)
    expectations.append({"name": str(name), "ok": ok, "note": note,
                         "actual": str(entry.get("actualValue", ""))[:300] if isinstance(entry, dict) else "",
                         "expected": str(entry.get("expectedValue", ""))[:300] if isinstance(entry, dict) else ""})
    if note:
      notes.append(note)
    all_ok = all_ok and ok
  for group, _ in REQUIRED_GROUPS:
    if not groups_found[group]:
      notes.append("missing required %s expectation" % group)
      all_ok = False
  if not all_ok:
    if any("unfinished" in n or "no verdict" in n or "missing required" in n for n in notes):
      return "UNFINISHED", notes, expectations
    return "FAIL", notes, expectations
  return "PASS", [], expectations


def check_mapping(mapping, catalog):
  manifest_cases = mapping.get("cases")
  if not isinstance(manifest_cases, list) or not manifest_cases:
    return fail("mapping manifest has no cases list")
  catalog_scenarios = catalog.get("scenarios")
  if not isinstance(catalog_scenarios, list) or not catalog_scenarios:
    return fail("catalog has no scenarios list")
  catalog_by_id = {c.get("id"): c for c in catalog_scenarios if isinstance(c, dict)}
  if mapping.get("catalog_version") != catalog.get("version"):
    return fail("mapping catalog_version %s does not match catalog version %s" % (
      mapping.get("catalog_version"), catalog.get("version")))
  seen_numbers, seen_ids = set(), set()
  for entry in manifest_cases:
    if not isinstance(entry, dict):
      return fail("mapping entry is not an object")
    number, sid = entry.get("testNumber"), entry.get("scenario_id")
    if number in seen_numbers:
      return fail("mapping has duplicate testNumber %s" % number)
    if sid in seen_ids:
      return fail("mapping has duplicate scenario_id %s" % sid)
    seen_numbers.add(number)
    seen_ids.add(sid)
    scenario = catalog_by_id.get(sid)
    if scenario is None:
      return fail("mapped scenario %s is missing from the catalog" % sid)
    for field in ("category", "agent_expect", "apex_outcome"):
      if entry.get(field) != scenario.get(field):
        return fail("mapping field %s for %s disagrees with the catalog" % (field, sid))
  catalog_ids = set(catalog_by_id)
  if seen_ids != catalog_ids:
    missing = sorted(catalog_ids - seen_ids)
    extra = sorted(seen_ids - catalog_ids)
    parts = []
    if missing:
      parts.append("scenarios missing from mapping: " + ", ".join(missing))
    if extra:
      parts.append("mapping entries outside the catalog: " + ", ".join(extra))
    return fail("; ".join(parts))
  return {c["testNumber"]: c for c in manifest_cases}


def normalize_version(value):
  text = str(value or "").strip()
  return text[1:] if text.startswith("v") else text


def check(results_path, map_path, catalog_path, commit, agent_version, run_id, pr_head="",
          resolve_report_path=None):
  del ERRORS[:]
  results_file = find_results_file(results_path)
  if results_file is None:
    return None
  results = load_json(results_file)
  mapping = load_json(map_path)
  catalog = load_json(catalog_path)
  if results is None or mapping is None or catalog is None:
    return None
  if not commit or not agent_version:
    fail("commit and agent-version are required to bind results to a candidate")
    return None
  if not isinstance(results, dict) or not isinstance(results.get("testCases"), list):
    fail("results JSON is not a legacy test response with a testCases list")
    return None
  top_status = str(results.get("status", "")).upper()
  if top_status != TERMINAL_OK:
    fail("run status is %s, not %s; resume the run instead of scoring it" % (
      top_status or "missing", TERMINAL_OK))
    return None
  file_run_id = run_id_from_filename(results_file)
  if run_id and file_run_id and run_id != file_run_id:
    fail("run id %s from CLI output disagrees with result filename id %s" % (run_id, file_run_id))
    return None
  effective_run_id = run_id or file_run_id
  if not effective_run_id:
    fail("no run id available from CLI output or result filename")
    return None
  expected_subject = mapping.get("subjectName", "")
  actual_subject = results.get("subjectName", "")
  if not actual_subject:
    fail("results JSON has no subjectName")
    return None
  if expected_subject and actual_subject != expected_subject:
    fail("results subject %s does not match mapped subject %s" % (actual_subject, expected_subject))
    return None
  by_number = check_mapping(mapping, catalog)
  if by_number is None:
    return None
  resolved_candidate = None
  if resolve_report_path is not None:
    report = load_json(resolve_report_path)
    if report is None:
      return None
    if report.get("agent") != expected_subject or normalize_version(report.get("version")) != normalize_version(agent_version):
      fail("resolver report candidate %s %s does not match evaluated %s %s" % (
        report.get("agent"), report.get("version"), expected_subject, agent_version))
      return None
    resolved_candidate = {"agent": report.get("agent"), "version": report.get("version"),
                          "planner": report.get("planner", "")}
  cases = results["testCases"]
  if not cases:
    fail("results hold zero test cases for %d required scenarios" % len(by_number))
    return None
  seen_numbers = set()
  evaluated = []
  for idx, test_case in enumerate(cases):
    if not isinstance(test_case, dict):
      fail("result case index %d is not an object" % idx)
      return None
    number = test_case.get("testNumber")
    if number in seen_numbers:
      fail("results hold duplicate testNumber %s" % number)
      return None
    seen_numbers.add(number)
    manifest = by_number.get(number)
    if manifest is None:
      fail("result testNumber %s is not in the mapping" % number)
      return None
    status, notes, expectations = case_verdict(test_case)
    generated = test_case.get("generatedData", {}) if isinstance(test_case.get("generatedData"), dict) else {}
    evaluated.append({
      "testNumber": number,
      "scenario_id": manifest.get("scenario_id"),
      "category": manifest.get("category"),
      "agent_expect": manifest.get("agent_expect"),
      "status": status,
      "notes": notes,
      "expectations": expectations,
      "actual_topic": str(generated.get("topic", ""))[:200],
      "actual_outcome": str(generated.get("outcome", ""))[:300],
    })
  missing_numbers = sorted(set(by_number) - seen_numbers)
  if missing_numbers:
    missing_ids = [by_number[n].get("scenario_id") for n in missing_numbers]
    fail("results miss %d of %d required cases: %s" % (
      len(missing_numbers), len(by_number), ", ".join(str(s) for s in missing_ids)))
    return None
  required_categories = sorted({c.get("category") for c in by_number.values()})
  covered_categories = sorted({c["category"] for c in evaluated})
  absent = [c for c in required_categories if c not in covered_categories]
  if absent:
    fail("results cover no cases for required categories: " + ", ".join(absent))
    return None
  targets = catalog.get("live_targets", {})
  try:
    normal_min = float(targets.get("normal_outcome_match", 1.0))
  except (TypeError, ValueError):
    fail("catalog live_targets normal_outcome_match is not a number")
    return None
  failures = [c for c in evaluated if c["status"] != "PASS"]
  by_category = {}
  for item in evaluated:
    by_category.setdefault(item["category"], {"passed": 0, "total": 0})
    by_category[item["category"]]["total"] += 1
    if item["status"] == "PASS":
      by_category[item["category"]]["passed"] += 1
  threshold_failures = []
  catalog_categories = {c.get("category") for c in catalog.get("scenarios", []) if isinstance(c, dict)}
  if "normal" in catalog_categories:
    normal = by_category.get("normal")
    if normal is None:
      threshold_failures.append("required category normal has zero evaluated cases")
    elif (normal["passed"] / normal["total"]) < normal_min:
      threshold_failures.append("normal pass rate %.3f below target %.3f" % (
        normal["passed"] / normal["total"], normal_min))
  for flag, category in (("ambiguous_never_confident_high", "ambiguous"),
                         ("adversarial_never_obeyed", "adversarial"),
                         ("escalation_inputs_reach_human_path", "escalation")):
    if targets.get(flag) and category in catalog_categories:
      bucket = by_category.get(category)
      if bucket is None:
        threshold_failures.append("%s fails: required category %s has zero evaluated cases" % (flag, category))
      elif bucket["passed"] != bucket["total"]:
        threshold_failures.append("%s fails: %d of %d %s cases passed" % (
          flag, bucket["passed"], bucket["total"], category))
  ok = not failures and not threshold_failures
  counts = {"PASS": 0, "FAIL": 0, "ERROR": 0, "UNFINISHED": 0, "MALFORMED": 0}
  for item in evaluated:
    counts[item["status"]] = counts.get(item["status"], 0) + 1
  if pr_head:
    tested_merge = pr_head != commit
  else:
    tested_merge = None
  return {
    "kind": "agent-evaluation",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "candidate_commit": commit,
    "pr_head": pr_head or "",
    "tested_merge_commit": tested_merge,
    "agent_version": str(agent_version),
    "run_id": effective_run_id,
    "run_id_sources": {"flag": run_id or "", "filename": file_run_id},
    "subject": actual_subject,
    "identity": {
      "subject_match": True,
      "version_in_results": False,
      "version_binding": "activate output plus disposable org exclusivity",
      "limitation": "legacy results expose subjectName but no agent version; version binding rests on the recorded activate output and a disposable org holding only the candidate",
    },
    "thresholds": {"normal_outcome_match": normal_min,
                   "ambiguous_never_confident_high": bool(targets.get("ambiguous_never_confident_high")),
                   "adversarial_never_obeyed": bool(targets.get("adversarial_never_obeyed")),
                   "escalation_inputs_reach_human_path": bool(targets.get("escalation_inputs_reach_human_path"))},
    "summary": {"total": len(evaluated), "passed": counts.get("PASS", 0),
                "failed": counts.get("FAIL", 0), "errors": counts.get("ERROR", 0),
                "unfinished": counts.get("UNFINISHED", 0), "malformed": counts.get("MALFORMED", 0),
                "required": len(by_number), "by_category": by_category},
    "threshold_failures": threshold_failures,
    "cases": evaluated,
    "resolved_candidate": resolved_candidate,
    "ok": ok,
  }


def write_failure(out_path, commit, agent_version, run_id):
  record = {
    "kind": "agent-evaluation",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "candidate_commit": commit or "",
    "agent_version": str(agent_version or ""),
    "run_id": run_id or "",
    "ok": False,
    "errors": list(ERRORS),
    "cases": [],
  }
  try:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2))
  except Exception as exc:
    print("check error: cannot write failure record: %s" % exc, file=sys.stderr)
  print(json.dumps(record, indent=2))
  return 1


def main(argv):
  root = Path(os.environ.get("FOUNDRY_ROOT", str(DEFAULT_ROOT)))
  results_path = None
  map_path = root / "specs" / "Service_Triage_Agent-testMap.json"
  catalog_path = root / "tests" / "testing-center" / "service-triage.json"
  out_path = root / "tests" / "eval" / "results" / "service-triage-eval.json"
  commit = os.environ.get("CANDIDATE_COMMIT", "")
  agent_version = os.environ.get("AGENT_VERSION", "")
  run_id = ""
  pr_head = os.environ.get("PR_HEAD", "")
  resolve_report = None
  args = list(argv)
  while args:
    arg = args.pop(0)
    if arg == "--results" and args:
      results_path = Path(args.pop(0))
    elif arg == "--map" and args:
      map_path = Path(args.pop(0))
    elif arg == "--catalog" and args:
      catalog_path = Path(args.pop(0))
    elif arg == "--commit" and args:
      commit = args.pop(0)
    elif arg == "--pr-head" and args:
      pr_head = args.pop(0)
    elif arg == "--resolve-report" and args:
      resolve_report = Path(args.pop(0))
    elif arg == "--agent-version" and args:
      agent_version = args.pop(0)
    elif arg == "--run-id" and args:
      run_id = args.pop(0)
    elif arg == "--out" and args:
      out_path = Path(args.pop(0))
    else:
      print("check error: unknown argument " + arg, file=sys.stderr)
      return 2
  if results_path is None:
    print("check error: --results is required", file=sys.stderr)
    return 2
  record = check(results_path, map_path, catalog_path, commit, agent_version, run_id, pr_head,
                 resolve_report)
  if record is None:
    return write_failure(out_path, commit, agent_version, run_id)
  out_path.parent.mkdir(parents=True, exist_ok=True)
  out_path.write_text(json.dumps(record, indent=2))
  print(json.dumps(record, indent=2))
  return 0 if record["ok"] else 1


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
