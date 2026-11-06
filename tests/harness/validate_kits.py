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
  base = ROOT / "force-app" / "main" / "default" / "classes"
  return {
    "action": (base / "ServiceTriageAction.cls").exists(),
    "test": (base / "ServiceTriageActionTest.cls").exists(),
    "sales_action": (base / "SalesQualificationAction.cls").exists(),
    "sales_test": (base / "SalesQualificationActionTest.cls").exists(),
    "it_action": (base / "InternalHelpAction.cls").exists(),
    "it_test": (base / "InternalHelpActionTest.cls").exists(),
  }

def run():
  kits = [check_kit(k) for k in KITS]
  apex = check_apex()
  ok = all(k["readme"] for k in kits) and all(apex.values())
  return {"kits": kits, "apex": apex, "ok": ok}

if __name__ == "__main__":
  print(json.dumps(run(), indent=2))
