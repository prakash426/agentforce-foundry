"""Unit tests for the Salesforce output verifier. No org needed."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIX = HERE / "fixtures" / "sf"
VERIFY = ROOT / "scripts" / "verify_sf_output.py"


def run(*args):
  proc = subprocess.run([sys.executable, str(VERIFY), *args],
                        capture_output=True, text=True)
  return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


class DeployVerifyTest(unittest.TestCase):
  def test_ok(self):
    code, out, _ = run("deploy", str(FIX / "deploy-ok.json"), "--check-only", "true")
    self.assertEqual(0, code)
    self.assertIn("0Af000000000001", out)

  def test_failed_rejected(self):
    code, _, err = run("deploy", str(FIX / "deploy-failed.json"))
    self.assertEqual(1, code)
    self.assertIn("not successful", err)

  def test_inprogress_rejected(self):
    code, _, err = run("deploy", str(FIX / "deploy-inprogress.json"))
    self.assertEqual(1, code)
    self.assertIn("InProgress", err)

  def test_check_only_mismatch_rejected(self):
    code, _, err = run("deploy", str(FIX / "deploy-real-ok.json"), "--check-only", "true")
    self.assertEqual(1, code)
    self.assertIn("checkOnly", err)


class ApexVerifyTest(unittest.TestCase):
  def test_ok(self):
    code, out, _ = run("apex", str(FIX / "apex-ok.json"))
    self.assertEqual(0, code)
    self.assertIn("707000000000001", out)

  def test_failures_rejected(self):
    code, _, err = run("apex", str(FIX / "apex-fail.json"))
    self.assertEqual(1, code)
    self.assertIn("apex failures", err)

  def test_async_without_summary_rejected(self):
    code, _, err = run("apex", str(FIX / "apex-async.json"))
    self.assertEqual(1, code)
    self.assertIn("unfinished", err)

  def test_zero_tests_rejected(self):
    code, _, err = run("apex", str(FIX / "apex-zero.json"))
    self.assertEqual(1, code)
    self.assertIn("zero tests", err)


class AgentVerifyTest(unittest.TestCase):
  def test_validate_ok(self):
    self.assertEqual(0, run("agent-validate", str(FIX / "validate-ok.json"))[0])

  def test_validate_errors_rejected(self):
    code, _, err = run("agent-validate", str(FIX / "validate-err.json"))
    self.assertEqual(1, code)
    self.assertIn("line 3", err)

  def test_publish_ok(self):
    code, out, _ = run("agent-publish", str(FIX / "publish-ok.json"))
    self.assertEqual(0, code)
    self.assertIn("Service_Triage_Agent", out)

  def test_publish_failed_rejected(self):
    self.assertEqual(1, run("agent-publish", str(FIX / "publish-err.json"))[0])

  def test_activate_ok(self):
    code, out, _ = run("agent-activate", str(FIX / "activate-ok.json"), "--expect-version", "2")
    self.assertEqual(0, code)
    self.assertIn("version=2", out)

  def test_activate_version_mismatch_rejected(self):
    code, _, err = run("agent-activate", str(FIX / "activate-ok.json"), "--expect-version", "3")
    self.assertEqual(1, code)
    self.assertIn("does not match", err)

  def test_activate_failed_rejected(self):
    self.assertEqual(1, run("agent-activate", str(FIX / "activate-err.json"))[0])

  def test_create_ok(self):
    self.assertEqual(0, run("agent-test-create", str(FIX / "testcreate-ok.json"))[0])

  def test_run_completed_ok(self):
    code, out, _ = run("agent-test-run", str(FIX / "testrun-ok.json"))
    self.assertEqual(0, code)
    self.assertIn("0HJ000000000001", out)

  def test_run_inprogress_rejected(self):
    code, _, err = run("agent-test-run", str(FIX / "testrun-inprogress.json"))
    self.assertEqual(1, code)
    self.assertIn("not COMPLETED", err)

  def test_generic_json_ok(self):
    self.assertEqual(0, run("json", str(FIX / "org-ok.json"))[0])

  def test_preview_start_ok(self):
    code, out, _ = run("preview-start", str(FIX / "preview-start-ok.json"),
                       "--expect-agent", "Service_Triage_Agent")
    self.assertEqual(0, code)
    self.assertEqual("sess-001", out)

  def test_preview_start_agent_mismatch_rejected(self):
    code, _, err = run("preview-start", str(FIX / "preview-start-ok.json"),
                       "--expect-agent", "Other")
    self.assertEqual(1, code)
    self.assertIn("does not match", err)

  def test_preview_send_ok(self):
    code, out, _ = run("preview-send", str(FIX / "preview-send-ok.json"),
                       "--expect-session", "sess-001")
    self.assertEqual(0, code)
    self.assertIn("messages=1", out)

  def test_preview_send_session_mismatch_rejected(self):
    code, _, err = run("preview-send", str(FIX / "preview-send-ok.json"),
                       "--expect-session", "sess-999")
    self.assertEqual(1, code)
    self.assertIn("does not match", err)


class AgentUserVerifyTest(unittest.TestCase):
  def test_create_ok(self):
    code, out, _ = run("agent-user-create", str(FIX / "agentuser-ok.json"))
    self.assertEqual(0, code)
    self.assertIn("agent.user.abc123@example.com", out)

  def test_create_perm_errors_rejected(self):
    code, _, err = run("agent-user-create", str(FIX / "agentuser-permfail.json"))
    self.assertEqual(1, code)
    self.assertIn("permission errors", err)

  def test_user_query_ok(self):
    code, out, _ = run("user-query", str(FIX / "userqry-ok.json"),
                       "--expect-username", "agent@example.com",
                       "--expect-profile", "Einstein Agent User")
    self.assertEqual(0, code)
    self.assertIn("005000000000001", out)

  def test_user_query_missing_rejected(self):
    code, _, err = run("user-query", str(FIX / "userqry-missing.json"),
                       "--expect-username", "agent@example.com",
                       "--expect-profile", "Einstein Agent User")
    self.assertEqual(1, code)
    self.assertIn("exactly one user", err)

  def test_user_query_inactive_rejected(self):
    code, _, err = run("user-query", str(FIX / "userqry-inactive.json"),
                       "--expect-username", "agent@example.com",
                       "--expect-profile", "Einstein Agent User")
    self.assertEqual(1, code)
    self.assertIn("not active", err)

  def test_user_query_profile_rejected(self):
    code, _, err = run("user-query", str(FIX / "userqry-profile.json"),
                       "--expect-username", "agent@example.com",
                       "--expect-profile", "Einstein Agent User")
    self.assertEqual(1, code)
    self.assertIn("Standard User", err)

  def test_assignment_query_ok(self):
    code, out, _ = run("assignment-query", str(FIX / "assign-full.json"),
                       "--expect", "AgentforceServiceAgentBase",
                       "--expect", "AgentforceServiceAgentUser",
                       "--expect", "EinsteinGPTPromptTemplateUser",
                       "--expect", "Agentforce_Foundry_Service")
    self.assertEqual(0, code)
    self.assertIn("Agentforce_Foundry_Service", out)

  def test_assignment_query_missing_rejected(self):
    code, _, err = run("assignment-query", str(FIX / "assign-thin.json"),
                       "--expect", "AgentforceServiceAgentBase",
                       "--expect", "AgentforceServiceAgentUser")
    self.assertEqual(1, code)
    self.assertIn("AgentforceServiceAgentUser", err)


class PublishDiffTest(unittest.TestCase):
  def test_single_new_version(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      before = Path(tmp) / "before.txt"
      after = Path(tmp) / "after.txt"
      before.write_text("v1.botVersion-meta.xml\n")
      after.write_text("v1.botVersion-meta.xml\nv2\nv2.botVersion-meta.xml\n")
      code, out, _ = run("publish-diff", str(before), str(after))
      self.assertEqual(0, code)
      self.assertEqual("v2", out)

  def test_no_new_version_rejected(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      before = Path(tmp) / "before.txt"
      after = Path(tmp) / "after.txt"
      before.write_text("v1\n")
      after.write_text("v1\n")
      self.assertEqual(1, run("publish-diff", str(before), str(after))[0])

  def test_ambiguous_new_versions_rejected(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      before = Path(tmp) / "before.txt"
      after = Path(tmp) / "after.txt"
      before.write_text("")
      after.write_text("v1\nv2\n")
      self.assertEqual(1, run("publish-diff", str(before), str(after))[0])


if __name__ == "__main__":
  unittest.main()
