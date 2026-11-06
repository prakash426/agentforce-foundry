"""Static audit of the Service Triage scenario catalog. No org needed.

Audits catalog completeness against static thresholds and cross checks
the fixtures file. Writes machine readable results. This is a static
audit, not a live agent evaluation. Live execution status is always
reported as pending by this runner. Exits nonzero when any check fails.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = DEFAULT_ROOT / "tests" / "eval" / "results"
CATEGORIES = {"normal", "ambiguous", "adversarial", "out_of_scope", "escalation"}


def audit(root):
  root = Path(root)
  checks = []

  def record(name, ok, detail):
    checks.append({"name": name, "ok": ok, "detail": detail})

  catalog_path = root / "tests" / "testing-center" / "service-triage.json"
  try:
    catalog = json.loads(catalog_path.read_text())
    record("catalog-parse", True, "catalog parses as JSON")
  except Exception as exc:
    record("catalog-parse", False, "catalog does not parse: " + str(exc))
    return finish(checks, {})
  scenarios = catalog.get("scenarios", [])
  min_per = catalog.get("static_thresholds", {}).get("min_scenarios_per_category", 2)
  counts = {}
  for case in scenarios:
    counts[case.get("category")] = counts.get(case.get("category"), 0) + 1
  thin = sorted(c for c in CATEGORIES if counts.get(c, 0) < min_per)
  if thin:
    record("category-coverage", False, "thin categories: " + ", ".join(thin))
  else:
    record("category-coverage", True, "every category has %d or more scenarios" % min_per)
  ids = [c.get("id") for c in scenarios]
  if len(ids) != len(set(ids)):
    record("unique-ids", False, "duplicate scenario ids present")
  else:
    record("unique-ids", True, "%d unique scenario ids" % len(ids))
  missing_notes = [c.get("id") for c in scenarios if not str(c.get("notes", "")).strip()]
  if missing_notes:
    record("scenario-notes", False, "scenarios without notes: " + ", ".join(missing_notes))
  else:
    record("scenario-notes", True, "every scenario documented")
  bad = [c.get("id") for c in scenarios
         if c.get("apex_outcome") == "SUGGESTED"
         and not (c.get("apex_priority") and c.get("apex_queue"))]
  if bad:
    record("suggested-complete", False, "SUGGESTED without priority and queue: " + ", ".join(bad))
  else:
    record("suggested-complete", True, "every SUGGESTED scenario has priority and queue")
  if "live_targets" not in catalog:
    record("live-targets", False, "catalog lacks live_targets block")
  else:
    record("live-targets", True, "live targets recorded as targets, not results")

  fixture_path = root / "tests" / "fixtures" / "service-triage-inputs.json"
  try:
    fixtures = json.loads(fixture_path.read_text())
    inputs = fixtures.get("inputs", [])
    valid = [i for i in inputs if isinstance(i, dict) and "subject" in i and "details" in i]
    if not valid:
      record("fixtures", False, "fixtures file has no usable subject and details pairs")
    else:
      record("fixtures", True, "%d synthetic inputs ready" % len(valid))
  except Exception as exc:
    record("fixtures", False, "fixtures do not parse: " + str(exc))
  return finish(checks, {"min_scenarios_per_category": min_per})


def finish(checks, thresholds):
  ok = all(c["ok"] for c in checks)
  return {
    "kind": "static-audit",
    "live_execution": "pending",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "thresholds": thresholds,
    "checks": checks,
    "ok": ok,
  }


def main(root, outdir):
  root, outdir = Path(root), Path(outdir)
  outcome = audit(root)
  outdir.mkdir(parents=True, exist_ok=True)
  (outdir / "service-triage-audit.json").write_text(json.dumps(outcome, indent=2))
  print(json.dumps(outcome, indent=2))
  return 0 if outcome["ok"] else 1


if __name__ == "__main__":
  root = Path(os.environ.get("FOUNDRY_ROOT", str(DEFAULT_ROOT)))
  outdir = Path(os.environ.get("FOUNDRY_OUT", str(DEFAULT_OUT)))
  sys.exit(main(root, outdir))
