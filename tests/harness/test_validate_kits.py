"""Focused check for offline validator."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_kits as v

class ValidatorTest(unittest.TestCase):
  def test_run_shape(self):
    out = v.run()
    self.assertIn("kits", out)
    self.assertIn("apex", out)
    self.assertIn("ok", out)
    self.assertEqual(3, len(out["kits"]))

  def test_service_kit_present(self):
    out = v.run()
    svc = [k for k in out["kits"] if k["kit"] == "service-triage"][0]
    self.assertTrue(svc["readme"])
    self.assertTrue(svc["suite"])

  def test_sales_kit_present(self):
    out = v.run()
    self.assertTrue(out["apex"]["sales_action"])
    self.assertTrue(out["apex"]["sales_test"])
    sq = [k for k in out["kits"] if k["kit"] == "sales-qualification"][0]
    self.assertTrue(sq["readme"])
    self.assertTrue(sq["suite"])

  def test_internal_kit_present(self):
    out = v.run()
    self.assertTrue(out["apex"]["it_action"])
    self.assertTrue(out["apex"]["it_test"])
    it = [k for k in out["kits"] if k["kit"] == "internal-help"][0]
    self.assertTrue(it["readme"])
    self.assertTrue(it["suite"])

if __name__ == "__main__":
  unittest.main()
