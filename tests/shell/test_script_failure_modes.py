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
  (bots / "v1.botVersion-meta.xml").write_text("<v1/>")
  (bots / "v2.botVersion-meta.xml").write_text("<v2/>")
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
                              "SF_FAIL_AT": "publish"})
      self.assertNotEqual(0, proc.returncode)
      self.assertNotIn("sf apex run test", log)
      agent_text = (proj / AGENT_REL).read_text()
      self.assertIn(PLACEHOLDER, agent_text)
      self.assertNotIn("agent@example.com", agent_text)

  def test_success_restores_agent_file_and_records_version(self):
    with tempfile.TemporaryDirectory() as tmp:
      proj, bindir = make_project(tmp)
      proc, log = run_script(proj, bindir, tmp, "setup-service-triage.sh",
                             {"DEV_HUB": "fake-hub", "AGENT_USER": "agent@example.com"})
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
