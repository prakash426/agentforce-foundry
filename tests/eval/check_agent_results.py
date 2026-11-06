"""Parse agent test run results and enforce acceptance thresholds.

Reads the JSON produced by sf agent test run with result-format json,
joins it to the converter mapping manifest and the committed catalog,
and writes a machine-readable evaluation record. Fails (exit nonzero)
when any required case errors or fails, when a threshold misses, or
when inputs are malformed. No org needed. Static audit, Apex unit
tests, and live agent evaluations stay separate: this script only
scores a live run, never the static catalog.

Inputs:
  --results PATH   agent test run JSON (file or directory holding one JSON file)
  --map PATH       converter mapping manifest (testMap.json)
  --catalog PATH   committed scenario catalog (service-triage.json)
  --commit SHA     candidate source commit the results prove
  --agent-version  published candidate agent version (for example v2 or 2)
  --run-id ID      optional test run identifier from the CLI
  --out PATH       evaluation record output (default tests/eval/results/service-triage-eval.json)

Thresholds come from the catalog live_targets block:
  normal_outcome_match is the minimum pass fraction across normal cases.
  ambiguous_never_confident_high, adversarial_never_obeyed, and
  escalation_inputs_reach_human_path each require every case in that
  category to pass, because the spec encodes the expected topic and
  actions per case. Any ERROR status fails immediately.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def fail(msg):
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
    cands = sorted(path.glob("*.json"))
    if len(cands) == 1:
      return cands[0]
    fail("results dir %s must hold exactly one JSON file, found %d" % (path, len(cands)))
    return None
  fail("results path missing: " + str(path))
  return None


def case_status(test_case):
  status = str(test_case.get("status", "")).upper()
  if status in ("PASS", "PASSED", "SUCCESS"):
    return "PASS"
  if status in ("FAIL", "FAILED"):
    return "FAIL"
  if status in ("ERROR",):
    return "ERROR"
  score = test_case.get("score")
  if isinstance(score, (int, float)):
    return "PASS" if score >= 1 else "FAIL"
  scorers = test_case.get("scorers")
  if isinstance(scorers, list) and scorers:
    bad = [s for s in scorers if str(s.get("status", "")).upper() not in ("PASS", "PASSED", "SUCCESS")]
    return "PASS" if not bad else "FAIL"
  return "UNKNOWN"


def extract_cases(results):
  if isinstance(results, dict) and isinstance(results.get("testCases"), list):
    return results["testCases"]
  if isinstance(results, dict) and isinstance(results.get("results"), dict):
    inner = results["results"].get("testCases")
    if isinstance(inner, list):
      return inner
  if isinstance(results, list):
    return results
  return None


def check(results_path, map_path, catalog_path, commit, agent_version, run_id):
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
  cases = extract_cases(results)
  if cases is None:
    fail("results JSON has no testCases list")
    return None
  manifest_cases = mapping.get("cases")
  if not isinstance(manifest_cases, list) or not manifest_cases:
    fail("mapping manifest has no cases list")
    return None
  by_number = {c.get("testNumber"): c for c in manifest_cases if isinstance(c, dict)}
  catalog_by_id = {c.get("id"): c for c in catalog.get("scenarios", []) if isinstance(c, dict)}
  evaluated = []
  for idx, test_case in enumerate(cases):
    if not isinstance(test_case, dict):
      fail("result case index %d is not an object" % idx)
      return None
    test_number = test_case.get("testNumber", idx + 1)
    manifest = by_number.get(test_number)
    if manifest is None:
      fail("result testNumber %s has no mapped scenario" % test_number)
      return None
    sid = manifest.get("scenario_id")
    scenario = catalog_by_id.get(sid)
    if scenario is None:
      fail("mapped scenario %s is missing from the catalog" % sid)
      return None
    status = case_status(test_case)
    evaluated.append({
      "testNumber": test_number,
      "scenario_id": sid,
      "category": manifest.get("category"),
      "agent_expect": manifest.get("agent_expect"),
      "status": status,
      "score": test_case.get("score"),
      "actual_topic": test_case.get("actualTopic", test_case.get("topic")),
      "actual_actions": test_case.get("actualActions", test_case.get("actions")),
      "detail": str(test_case.get("message", test_case.get("detail", "")))[:500],
    })
  targets = catalog.get("live_targets", {})
  normal_min = float(targets.get("normal_outcome_match", 1.0))
  failures = [c for c in evaluated if c["status"] != "PASS"]
  errors = [c for c in evaluated if c["status"] == "ERROR"]
  unknowns = [c for c in evaluated if c["status"] == "UNKNOWN"]
  by_category = {}
  for item in evaluated:
    by_category.setdefault(item["category"], {"passed": 0, "total": 0})
    by_category[item["category"]]["total"] += 1
    if item["status"] == "PASS":
      by_category[item["category"]]["passed"] += 1
  threshold_failures = []
  normal = by_category.get("normal", {"passed": 0, "total": 0})
  normal_rate = (normal["passed"] / normal["total"]) if normal["total"] else 1.0
  if normal_rate < normal_min:
    threshold_failures.append("normal pass rate %.3f below target %.3f" % (normal_rate, normal_min))
  for flag, category in (("ambiguous_never_confident_high", "ambiguous"),
                         ("adversarial_never_obeyed", "adversarial"),
                         ("escalation_inputs_reach_human_path", "escalation")):
    if targets.get(flag):
      bucket = by_category.get(category, {"passed": 0, "total": 0})
      if bucket["passed"] != bucket["total"]:
        threshold_failures.append("%s fails: %d of %d %s cases passed" % (
          flag, bucket["passed"], bucket["total"], category))
  ok = not failures and not threshold_failures and not unknowns
  record = {
    "kind": "agent-evaluation",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "candidate_commit": commit,
    "agent_version": str(agent_version),
    "run_id": run_id or results.get("runId", results.get("run_id", "")),
    "subject": results.get("subjectName", mapping.get("subjectName", "")),
    "thresholds": {"normal_outcome_match": normal_min,
                   "ambiguous_never_confident_high": bool(targets.get("ambiguous_never_confident_high")),
                   "adversarial_never_obeyed": bool(targets.get("adversarial_never_obeyed")),
                   "escalation_inputs_reach_human_path": bool(targets.get("escalation_inputs_reach_human_path"))},
    "summary": {"total": len(evaluated), "passed": len(evaluated) - len(failures),
                "failed": len([c for c in failures if c["status"] == "FAIL"]),
                "errors": len(errors), "unknown": len(unknowns),
                "by_category": by_category},
    "threshold_failures": threshold_failures,
    "cases": evaluated,
    "ok": ok,
  }
  return record


def main(argv):
  root = Path(os.environ.get("FOUNDRY_ROOT", str(DEFAULT_ROOT)))
  results_path = None
  map_path = root / "specs" / "Service_Triage_Agent-testMap.json"
  catalog_path = root / "tests" / "testing-center" / "service-triage.json"
  out_path = root / "tests" / "eval" / "results" / "service-triage-eval.json"
  commit = os.environ.get("CANDIDATE_COMMIT", "")
  agent_version = os.environ.get("AGENT_VERSION", "")
  run_id = ""
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
  record = check(results_path, map_path, catalog_path, commit, agent_version, run_id)
  if record is None:
    return 1
  out_path.parent.mkdir(parents=True, exist_ok=True)
  out_path.write_text(json.dumps(record, indent=2))
  print(json.dumps(record, indent=2))
  return 0 if record["ok"] else 1


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
