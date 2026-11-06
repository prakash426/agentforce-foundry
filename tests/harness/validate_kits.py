"""Offline validator for Foundry kits. No org needed."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KITS = ["service-triage", "sales-qualification", "internal-help"]

def check_kit(name):
  base = ROOT / "kits" / name
  return {
    "kit": name,
    "readme": (base / "README.md").exists(),
    "suite": (ROOT / "tests" / "testing-center" / f"{name}.json").exists(),
  }

def check_apex():
  cls = ROOT / "force-app" / "main" / "default" / "classes" / "ServiceTriageAction.cls"
  tst = ROOT / "force-app" / "main" / "default" / "classes" / "ServiceTriageActionTest.cls"
  return {"action": cls.exists(), "test": tst.exists()}

def run():
  kits = [check_kit(k) for k in KITS]
  apex = check_apex()
  ok = all(k["readme"] for k in kits) and apex["action"] and apex["test"]
  return {"kits": kits, "apex": apex, "ok": ok}

if __name__ == "__main__":
  print(json.dumps(run(), indent=2))
