"""Mocked failure tests for org scripts. No credentials, no org.

Builds a miniature project with a fake sf CLI on PATH, runs the real
scripts, and proves that failures stop later steps, outputs are kept,
unfinished async work fails explicitly, and the agent file placeholder
is restored. Interruption shares the EXIT trap path, which the failure
cases exercise.
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AGENT_REL = "force-app/main/default/aiAuthoringBundles/Service_Triage_Agent/Service_Triage_Agent.agent"
PLACEHOLDER = "UPDATE_WITH_DEFAULT_AGENT_USER"


def make_project(tmp):
  proj = Path(tmp) / "proj"
  (proj / "config").mkdir(parents=True)
  (proj / "config" / "project-scratch-def.json").write_text("{}")
  agent = proj / AGENT_REL
  agent.parent.mkdir(parents=True, exist_ok=True)
  agent.write_text('config:\n    default_agent_user: "%s"\n' % PLACEHOLDER)
  bots = proj / "force-app/main/default/bots/Service_Triage_Agent"
  bots.mkdir(parents=True, exist_ok=True)
  (bots / "v1.botVersion-meta.xml").write_text(
    "<BotVersion><conversationDefinitionPlanners><genAiPlannerName>PlannerV1</genAiPlannerName>"
    "</conversationDefinitionPlanners></BotVersion>")
  (bots / "v2.botVersion-meta.xml").write_text(
    "<BotVersion><conversationDefinitionPlanners><genAiPlannerName>PlannerV2</genAiPlannerName>"
    "</conversationDefinitionPlanners></BotVersion>")
  versions = proj / "force-app/main/default/aiAgentDefinitionVersions"
  for num in ("1", "2"):
    vdir = versions / ("Service_Triage_Agent#%s" % num)
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / ("Service_Triage_Agent#%s.aiAgentDefinitionVersion-meta.xml" % num)).write_text(
      '<AiAgentDefinitionVersion><genAiPlannerName>Planner%s</genAiPlannerName>'
      '<version>%s</version></AiAgentDefinitionVersion>' % (num, num))
  bundle = proj / "force-app/main/default/genAiPlannerBundles"
  bundle.mkdir(parents=True, exist_ok=True)
  links = "".join("<localTopicLinks><genAiPluginName>%s</genAiPluginName></localTopicLinks>" % n
                  for n in ("triage_case", "ambiguous_request", "off_topic", "escalation"))
  (bundle / "PlannerV2.genAiPlannerBundle-meta.xml").write_text(
    "<GenAiPlannerBundle>" + links +
    "<localTopics><localActionLinks><functionName>triage_service_case</functionName>"
    "</localActionLinks></localTopics></GenAiPlannerBundle>")
  plugins = proj / "force-app/main/default/genAiPlugins"
  plugins.mkdir(parents=True, exist_ok=True)
  for name in ("triage_case", "ambiguous_request", "off_topic", "escalation"):
    (plugins / (name + ".genAiPlugin-meta.xml")).write_text(
      '<GenAiPlugin><genAiFunctions><functionName>triage_service_case</functionName>'
      "</genAiFunctions></GenAiPlugin>")
  shutil.copytree(ROOT / "scripts", proj / "scripts")
  shutil.copytree(ROOT / "tests" / "eval", proj / "tests" / "eval")
  shutil.copytree(ROOT / "tests" / "testing-center", proj / "tests" / "testing-center")
  (proj / "specs").mkdir()
  bindir = Path(tmp) / "bin"
  bindir.mkdir()
  fake = bindir / "sf"
  shutil.copy(HERE / "fake_sf.sh", fake)
  fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
  (Path(tmp) / "sf.log").write_text("")
  return proj, bindir


def run_script(proj, bindir, tmp, name, env_extra=None):
  env = dict(os.environ)
  env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
  env["SF_LOG"] = str(Path(tmp) / "sf.log")
  env["SF_FIXTURE_DIR"] = str(HERE / "fixtures" / "sf")
  env.update(env_extra or {})
  proc = subprocess.run(["bash", "scripts/" + name], cwd=str(proj),
                        capture_output=True, text=True, env=env)
  log = (Path(tmp) / "sf.log").read_text()
  return proc, log


class SetupFailureTest(unittest.TestCase):
  def test_deploy_failure_stops_later_steps(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"DEV_HUB": "fake-hub", "SF_FAIL_AT": "deploy"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("sf project deploy start", log)
      self.assertNotIn("sf apex run test", log)
      self.assertNotIn("sf agent publish", log)
      out = (proj / "deploy-deps-foundry-triage.json").read_text()
      self.assertIn("injected failure", out)

  def test_publish_failure_restores_agent_file(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"DEV_HUB": "fake-hub", "AGENT_USER": "agent@example.com",
                              "SF_FAIL_AT": "publish", "SF_ASSIGN_MODE": "full"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf apex run test", log)
      agent_text = (proj / AGENT_REL).read_text()
      self.assertIn(PLACEHOLDER, agent_text)
      self.assertNotIn("agent@example.com", agent_text)

  def test_success_restores_agent_file_and_records_version(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"DEV_HUB": "fake-hub", "AGENT_USER": "agent@example.com",
                              "SF_ASSIGN_MODE": "full"})
      self.assertEqual(0, proc.returncode, msg=proc.stderr + proc.stdout)
      self.assertIn("sf apex run test", log)
      agent_text = (proj / AGENT_REL).read_text()
      self.assertIn(PLACEHOLDER, agent_text)
      self.assertNotIn("agent@example.com", agent_text)
      version = (proj / "candidate-version-Service_Triage_Agent.txt").read_text().strip()
      self.assertEqual("v3", version)

  def test_unfinished_apex_fails_despite_zero_exit(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, _ = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                           {"DEV_HUB": "fake-hub", "SF_APEX_MODE": "apex-async"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("unfinished", proc.stdout + proc.stderr)

  def test_failing_apex_stops_activation(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"DEV_HUB": "fake-hub", "SF_APEX_MODE": "apex-fail",
                              "ACTIVATE": "1", "AGENT_VERSION": "3"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf agent activate", log)


class SetupAgentUserTest(unittest.TestCase):
  def test_create_success_captures_username(self):
    import json
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                             {"ORG_ALIAS": "fake-org"})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      record = json.loads((proj / "agent-user-fake-org.json").read_text())
      self.assertEqual("agent.user.abc123@example.com", record["username"])
      self.assertEqual("created", record["mode"])
      self.assertIn("sf org create agent-user", log)
      self.assertIn("sf org assign permset -n Agentforce_Foundry_Service -o fake-org -b agent.user.abc123@example.com", log)

  def test_existing_user_verified(self):
    import json
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                             {"ORG_ALIAS": "fake-org", "AGENT_USER": "agent@example.com",
                              "SF_ASSIGN_MODE": "full"})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      record = json.loads((proj / "agent-user-fake-org.json").read_text())
      self.assertEqual("existing", record["mode"])
      self.assertNotIn("sf org create agent-user", log)

  def test_existing_user_gets_custom_permset(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                             {"ORG_ALIAS": "fake-org", "AGENT_USER": "agent@example.com",
                              "SF_ASSIGN_MODE": "platform"})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      self.assertIn("-b agent@example.com", log)

  def test_missing_user_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                             {"ORG_ALIAS": "fake-org", "AGENT_USER": "ghost@example.com",
                              "SF_USER_MODE": "missing"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf org assign permset", log)

  def test_inactive_user_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, _ = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                           {"ORG_ALIAS": "fake-org", "AGENT_USER": "agent@example.com",
                            "SF_USER_MODE": "inactive"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("not active", proc.stdout + proc.stderr)

  def test_wrong_profile_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, _ = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                           {"ORG_ALIAS": "fake-org", "AGENT_USER": "agent@example.com",
                            "SF_USER_MODE": "profile"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("Standard User", proc.stdout + proc.stderr)

  def test_missing_platform_permsets_fails(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, _ = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                           {"ORG_ALIAS": "fake-org", "AGENT_USER": "agent@example.com",
                            "SF_ASSIGN_MODE": "thin"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("platform permission sets", proc.stdout + proc.stderr)

  def test_failed_creation_stops(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                             {"ORG_ALIAS": "fake-org", "SF_FAIL_AT": "agent-user"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf org assign permset", log)
      self.assertFalse((proj / "agent-user-fake-org.json").exists())

  def test_failed_assignment_stops(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, _ = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                           {"ORG_ALIAS": "fake-org", "SF_FAIL_AT": "assign"})
      self.assertNotEqual(0, proc.returncode)
      self.assertFalse((proj / "agent-user-fake-org.json").exists())

  def test_user_failure_blocks_publish(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"DEV_HUB": "fake-hub", "SF_FAIL_AT": "agent-user"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf agent validate", log)
      self.assertNotIn("sf agent publish", log)
      agent_text = (proj / AGENT_REL).read_text()
      self.assertIn(PLACEHOLDER, agent_text)

  def test_create_path_success_end_to_end(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"DEV_HUB": "fake-hub"})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      self.assertIn("sf org create agent-user", log)
      self.assertIn("sf agent publish", log)
      agent_text = (proj / AGENT_REL).read_text()
      self.assertIn(PLACEHOLDER, agent_text)
      self.assertNotIn("abc123", agent_text)


class StderrWarningTest(unittest.TestCase):
  WARN = "Warning: @salesforce/cli update available from 2.145.6 to 2.157.8."

  def test_stderr_warning_does_not_break_verification(self):
    import json
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-agent-user.sh",
                             {"ORG_ALIAS": "fake-org", "SF_STDERR_WARN": self.WARN})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      record = json.loads((proj / "agent-user-fake-org.json").read_text())
      self.assertEqual("agent.user.abc123@example.com", record["username"])
      kept = (proj / "agent-user-create-fake-org.json").read_text()
      self.assertNotIn("update available", kept)

  def test_stderr_warning_does_not_break_setup(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, _ = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                           {"USE_EXISTING_ORG": "1", "ORG_ALIAS": "fake-org",
                            "AGENT_USER": "agent@example.com",
                            "SF_ASSIGN_MODE": "full", "SF_STDERR_WARN": self.WARN})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      kept = (proj / "org-display-fake-org.json").read_text()
      self.assertNotIn("update available", kept)


class CreateTestFailureTest(unittest.TestCase):
  BASE = {"ORG_ALIAS": "fake-org", "AGENT_VERSION": "2", "RUN_TEST": "1"}

  def test_run_failure_skips_scoring(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      env = dict(self.BASE, SF_FAIL_AT="run")
      proc, log = run_script(proj, bindir, tmp, "create-service-triage-test.sh", env)
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("sf agent test run", log)
      self.assertFalse((proj / "tests" / "eval" / "results" / "service-triage-eval.json").exists())

  def test_inprogress_run_fails_despite_zero_exit(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      env = dict(self.BASE, SF_RUN_MODE="testrun-inprogress")
      proc, _ = run_script(proj, bindir, tmp, "create-service-triage-test.sh", env)
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("not COMPLETED", proc.stdout + proc.stderr)

  def test_missing_version_file_fails_before_create(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      env = dict(self.BASE, AGENT_VERSION="9")
      proc, log = run_script(proj, bindir, tmp, "create-service-triage-test.sh", env)
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf agent test create", log)


class PreviewTurnsTest(unittest.TestCase):
  TURNS = {"sequences": [{"name": "trio", "turns": [
    {"utterance": "one"},
    {"utterance": "two", "expect_any": ["Suggested"]},
    {"utterance": "three"},
  ]}]}

  def write_turns(self, proj):
    import json
    path = proj / "turns.json"
    path.write_text(json.dumps(self.TURNS))
    return path

  def send_lines(self, log):
    return [line for line in log.splitlines() if "agent preview send" in line]

  def test_published_mode(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      turns = self.write_turns(proj)
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(turns)})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      self.assertIn("sf agent preview start -o fake-org --json -n Service_Triage_Agent", log)
      sends = self.send_lines(log)
      self.assertEqual(3, len(sends))
      for line in sends:
        self.assertIn("-n Service_Triage_Agent", line)
        self.assertIn("--session-id sess-001", line)
        self.assertNotIn("use-live-actions", line)
        self.assertNotIn("simulate-actions", line)
      self.assertIn("sf agent preview end", log)
      transcript = (proj / "preview-transcripts" / "trio-transcript.jsonl").read_text().splitlines()
      self.assertEqual(3, len(transcript))

  def test_live_bundle_mode(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      turns = self.write_turns(proj)
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(turns),
                              "TARGET": "bundle", "ACTIONS": "live"})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      self.assertIn("--authoring-bundle Service_Triage_Agent --use-live-actions", log)
      for line in self.send_lines(log):
        self.assertIn("--authoring-bundle Service_Triage_Agent", line)
        self.assertNotIn("use-live-actions", line)
        self.assertNotIn("simulate-actions", line)

  def test_simulated_bundle_mode(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      turns = self.write_turns(proj)
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(turns),
                              "TARGET": "bundle", "ACTIONS": "simulate"})
      self.assertEqual(0, proc.returncode, msg=proc.stdout + proc.stderr)
      self.assertIn("--authoring-bundle Service_Triage_Agent --simulate-actions", log)
      for line in self.send_lines(log):
        self.assertNotIn("use-live-actions", line)
        self.assertNotIn("simulate-actions", line)

  def test_invalid_modes_rejected_before_session(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      turns = self.write_turns(proj)
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(turns), "TARGET": "nope"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("agent preview start", log)
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(turns), "ACTIONS": "nope"})
      self.assertNotEqual(0, proc.returncode)

  def test_failed_send_ends_session_and_keeps_transcript(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      turns = self.write_turns(proj)
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(turns),
                              "SF_FAIL_AT": "preview-send"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("sf agent preview end", log)
      transcript = (proj / "preview-transcripts" / "trio-transcript.jsonl").read_text().splitlines()
      self.assertEqual(0, len([line for line in transcript if line.strip()]))

  def test_smoke_miss_fails_but_keeps_transcript(self):
    import copy
    import json
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      turns = copy.deepcopy(self.TURNS)
      turns["sequences"][0]["turns"][1]["expect_any"] = ["NoSuchPhrase"]
      path = proj / "turns.json"
      path.write_text(json.dumps(turns))
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(path)})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("smoke check", proc.stdout + proc.stderr)
      transcript = (proj / "preview-transcripts" / "trio-transcript.jsonl").read_text().splitlines()
      self.assertEqual(3, len(transcript))


class AgentCommandGateTest(unittest.TestCase):
  def test_setup_blocked_before_any_org_call(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"USE_EXISTING_ORG": "1", "ORG_ALIAS": "fake-org",
                              "SF_NO_AGENT_CMDS": "1"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("2.157.8", proc.stdout + proc.stderr)
      self.assertNotIn("sf org display", log)
      self.assertNotIn("sf project deploy", log)

  def test_preview_blocked_before_session(self):
    import json
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      turns = proj / "turns.json"
      turns.write_text(json.dumps({"sequences": [{"name": "one", "turns": [
        {"utterance": "hi"}]}]}))
      proc, log = run_script(proj, bindir, tmp, "preview-service-triage-turns.sh",
                             {"ORG_ALIAS": "fake-org", "TURNS": str(turns),
                              "SF_NO_AGENT_CMDS": "1"})
      self.assertNotEqual(0, proc.returncode)
      self.assertIn("2.157.8", proc.stdout + proc.stderr)
      self.assertNotIn("agent preview start", log)


class SetupAllFailureTest(unittest.TestCase):
  def test_deploy_failure_stops_tests(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup.sh",
                             {"DEV_HUB": "fake-hub", "SF_FAIL_AT": "deploy"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf apex run test", log)


if __name__ == "__main__":
  unittest.main()
