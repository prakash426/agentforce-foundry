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


class CliNoiseTest(unittest.TestCase):
  WARN = " \u203a   Warning: @salesforce/cli update available from \u001b[92m2.145.6\u001b[39m to \u001b[92m2.157.8\u001b[39m.\n"

  def test_leading_warning_preamble_accepted(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      noisy = Path(tmp) / "org-warn.json"
      noisy.write_text(self.WARN + (FIX / "org-ok.json").read_text())
      code, out, _ = run("json", str(noisy))
      self.assertEqual(0, code)
      self.assertIn("status=0", out)

  def test_leading_warning_preamble_accepted_for_apex(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      noisy = Path(tmp) / "apex-warn.json"
      noisy.write_text(self.WARN + (FIX / "apex-ok.json").read_text())
      code, out, _ = run("apex", str(noisy))
      self.assertEqual(0, code)
      self.assertIn("707000000000001", out)

  def test_pure_garbage_rejected(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      bad = Path(tmp) / "bad.json"
      bad.write_text("injected failure at deploy\n")
      self.assertEqual(1, run("json", str(bad))[0])

  def test_trailing_garbage_rejected(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      bad = Path(tmp) / "trailing.json"
      bad.write_text((FIX / "org-ok.json").read_text() + "\nunexpected trailer\n")
      self.assertEqual(1, run("json", str(bad))[0])


class PublishDiffTest(unittest.TestCase):
  AGENT = "Service_Triage_Agent"

  def diff(self, before_text, after_text, agent=None):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      before = Path(tmp) / "before.txt"
      after = Path(tmp) / "after.txt"
      before.write_text(before_text)
      after.write_text(after_text)
      chosen = self.AGENT if agent is None else agent
      return run("publish-diff", "--expect-agent", chosen, str(before), str(after))

  def test_single_new_version(self):
    code, out, _ = self.diff("v1.botVersion-meta.xml\n",
                             "v1.botVersion-meta.xml\nv2\nv2.botVersion-meta.xml\n")
    self.assertEqual(0, code)
    self.assertEqual("v2", out)

  def test_no_new_version_rejected(self):
    code, _, err = self.diff("v1\n", "v1\n")
    self.assertEqual(1, code)
    self.assertIn("none", err)

  def test_ambiguous_new_versions_rejected(self):
    code, _, err = self.diff("", "v1\nv2\n")
    self.assertEqual(1, code)
    self.assertIn("v1, v2", err)

  def test_hash_layout_new_version(self):
    code, out, _ = self.diff("Service_Triage_Agent#1\nService_Triage_Agent#2\n",
                             "Service_Triage_Agent#1\nService_Triage_Agent#2\nService_Triage_Agent#3\n")
    self.assertEqual(0, code)
    self.assertEqual("v3", out)

  def test_mixed_layouts_new_version(self):
    code, out, _ = self.diff(
      "v1.botVersion-meta.xml\nv2.botVersion-meta.xml\nService_Triage_Agent#1\nService_Triage_Agent#2\n",
      "v1.botVersion-meta.xml\nv2.botVersion-meta.xml\nService_Triage_Agent#1\nService_Triage_Agent#2\nService_Triage_Agent#3\n")
    self.assertEqual(0, code)
    self.assertEqual("v3", out)

  def test_missing_retrieval_rejected(self):
    code, _, err = self.diff("", "")
    self.assertEqual(1, code)
    self.assertIn("missing selected agent", err)

  def test_exact_two_agent_collision(self):
    code, out, _ = self.diff("OtherAgent#2\nService_Triage_Agent#1\n",
                             "OtherAgent#2\nService_Triage_Agent#1\nService_Triage_Agent#2\n")
    self.assertEqual(0, code)
    self.assertEqual("v2", out)

  def test_other_agent_publishing_alone_fails(self):
    code, _, err = self.diff("OtherAgent#1\nService_Triage_Agent#1\n",
                             "OtherAgent#1\nOtherAgent#2\nService_Triage_Agent#1\n")
    self.assertEqual(1, code)
    self.assertIn("none", err)
    self.assertIn("Service_Triage_Agent", err)

  def test_two_agents_same_new_version(self):
    code, out, _ = self.diff("OtherAgent#1\nService_Triage_Agent#1\n",
                             "OtherAgent#1\nOtherAgent#2\nService_Triage_Agent#1\nService_Triage_Agent#2\n")
    self.assertEqual(0, code)
    self.assertEqual("v2", out)

  def test_multiple_new_selected_versions_rejected(self):
    code, _, err = self.diff("Service_Triage_Agent#1\n",
                             "Service_Triage_Agent#1\nService_Triage_Agent#2\nService_Triage_Agent#3\n")
    self.assertEqual(1, code)
    self.assertIn("v2, v3", err)

  def test_missing_selected_agent_rejected(self):
    code, _, err = self.diff("OtherAgent#1\n", "OtherAgent#1\nOtherAgent#2\n")
    self.assertEqual(1, code)
    self.assertIn("missing selected agent", err)

  def test_similar_names_do_not_match(self):
    code, _, err = self.diff(
      "Service_Triage_Agent#1\n",
      "Service_Triage_Agent#1\nService_Triage_Agent_Extra#2\nService_Triage_Agent2#2\nservice_triage_agent#2\n")
    self.assertEqual(1, code)
    self.assertIn("none", err)

  def test_conflicting_removed_version_rejected(self):
    code, _, err = self.diff("Service_Triage_Agent#1\nService_Triage_Agent#2\n",
                             "Service_Triage_Agent#1\n")
    self.assertEqual(1, code)
    self.assertIn("conflicting", err)

  def test_malformed_expected_token_rejected(self):
    code, _, err = self.diff("Service_Triage_Agent#1\n",
                             "Service_Triage_Agent#1\nService_Triage_Agent#x\n")
    self.assertEqual(1, code)
    self.assertIn("malformed", err)

  def test_no_blind_highest_version(self):
    code, _, err = self.diff("Service_Triage_Agent#1\nService_Triage_Agent#3\n",
                             "Service_Triage_Agent#1\nService_Triage_Agent#3\n")
    self.assertEqual(1, code)
    self.assertIn("none", err)

  def test_missing_agent_flag_rejected(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      before = Path(tmp) / "before.txt"
      after = Path(tmp) / "after.txt"
      before.write_text("Service_Triage_Agent#1\n")
      after.write_text("Service_Triage_Agent#1\nService_Triage_Agent#2\n")
      code, _, err = run("publish-diff", str(before), str(after))
      self.assertEqual(1, code)
      self.assertIn("expect-agent", err)

  def test_invalid_agent_rejected(self):
    code, _, err = self.diff("Service_Triage_Agent#1\n",
                             "Service_Triage_Agent#1\nService_Triage_Agent#2\n",
                             agent="bad-name!")
    self.assertEqual(1, code)
    self.assertIn("valid API name", err)


class AssignmentListTest(unittest.TestCase):
  def test_full_lists_custom(self):
    code, out, _ = run("assignment-list", str(FIX / "assign-full.json"))
    self.assertEqual(0, code)
    self.assertIn("Agentforce_Foundry_Service", out)

  def test_thin_lists_without_custom(self):
    code, out, _ = run("assignment-list", str(FIX / "assign-thin.json"))
    self.assertEqual(0, code)
    self.assertNotIn("Agentforce_Foundry_Service", out)

  def test_malformed_rejected(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      bad = Path(tmp) / "bad.json"
      bad.write_text('{"status": 0, "result": {}}')
      code, _, err = run("assignment-list", str(bad))
      self.assertEqual(1, code)
      self.assertIn("no records list", err)


class PermsetDuplicateTest(unittest.TestCase):
  def test_duplicate_accepted(self):
    code, out, _ = run("permset-duplicate", str(FIX / "permset-duplicate.json"))
    self.assertEqual(0, code)
    self.assertIn("already-assigned", out)

  def test_success_rejected(self):
    code, _, _ = run("permset-duplicate", str(FIX / "org-ok.json"))
    self.assertEqual(1, code)

  def test_genuine_failure_rejected(self):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
      bad = Path(tmp) / "bad.json"
      bad.write_text('{"status": 1, "result": {"successes": [], '
                     '"failures": [{"name": "a@b.c", "message": "INVALID_OR_NULL_FOR_FIELD"}]}}')
      code, _, err = run("permset-duplicate", str(bad))
      self.assertEqual(1, code)
      self.assertIn("not a duplicate", err)


if __name__ == "__main__":
  unittest.main()
