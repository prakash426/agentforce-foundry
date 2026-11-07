"""Verify Salesforce CLI JSON outputs instead of trusting exit codes or files.

Every subcommand reads one CLI JSON document, requires the success
markers the platform actually returns, prints the extracted identity
(deployment id, test run id, version), and exits nonzero on anything
else: failures, unfinished async work, or malformed output. Shapes are
verified against installed plugin sources:

- deploy: MetadataRequestStatus carries id, status, success, done.
  RequestStatus runs Pending, InProgress, Succeeded, and the rest.
- apex: a completed run carries result.summary with outcome, passing,
  failing, skipped, testsRan, and testRunId, plus a tests list with
  per-test outcome values Pass, Fail, CompileFail, Skip. An async
  timeout returns only a test run id with no summary and exit zero,
  so summary presence is required explicitly. Failures set a nonzero
  exit via summary outcome Failed; this check enforces the same rule
  on the payload itself.
- agent-validate and agent-publish: a success boolean plus errors.
  Publish adds botDeveloperName and retrieved/deployed components.
- agent-activate: a success boolean plus the activated version number.
- agent-test-run: run stdout carries status plus runId. Assertion
  failures exit zero by design, so completion here means status
  COMPLETED with a run id; the eval checker scores the assertions.
- agent-test-create: a path plus contents for the synced metadata.
- preview-start: a sessionId plus the agent api name.
- preview-send: a messages list plus the echoed session id.
- agent-user-create: a userId plus username with empty permission errors
  and all three platform permission sets assigned.
- user-query: exactly one active user record with the expected profile.
- assignment-query: permission set assignments covering expected names.
- json: generic oclif envelope with top-level status zero.

Usage: python3 scripts/verify_sf_output.py <subcommand> <file> [options]
"""
import json
import sys
from pathlib import Path


def fail(msg):
  print("verify error: " + msg, file=sys.stderr)
  return 1


def load(path):
  try:
    return json.loads(Path(path).read_text())
  except Exception as exc:
    print("verify error: cannot parse %s: %s" % (path, exc), file=sys.stderr)
    return None


def unwrap(data):
  if isinstance(data, dict) and isinstance(data.get("result"), dict):
    return data["result"]
  return data


def cmd_deploy(args):
  expect_check_only = None
  rest = []
  it = iter(args)
  for arg in it:
    if arg == "--check-only":
      try:
        expect_check_only = next(it).lower() in ("true", "yes", "1")
      except StopIteration:
        return fail("deploy needs a value after --check-only")
    else:
      rest.append(arg)
  if len(rest) != 1:
    return fail("usage: deploy <file> [--check-only true|false]")
  data = load(rest[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict):
    return fail("deploy output has no result object")
  status = result.get("status")
  if status != "Succeeded" or result.get("success") is not True or result.get("done") is not True:
    return fail("deploy not successful: status=%s success=%s done=%s id=%s" % (
      status, result.get("success"), result.get("done"), result.get("id", "unknown")))
  check_only = result.get("checkOnly")
  if expect_check_only is not None and bool(check_only) is not expect_check_only:
    return fail("deploy checkOnly=%s, expected %s" % (check_only, expect_check_only))
  print("deploy id=%s status=%s tests=%s/%s checkOnly=%s" % (
    result.get("id"), status, result.get("numberTestsCompleted"),
    result.get("numberTestsTotal"), check_only))
  return 0


def cmd_apex(args):
  if len(args) != 1:
    return fail("usage: apex <file>")
  data = load(args[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict):
    return fail("apex output has no result object")
  summary = result.get("summary")
  if not isinstance(summary, dict):
    run_id = result.get("testRunId", "unknown")
    return fail("apex run unfinished (no summary, async run %s); rerun after completion" % run_id)
  tests_ran = summary.get("testsRan", 0)
  failing = summary.get("failing", 0)
  if not isinstance(tests_ran, int) or tests_ran <= 0:
    return fail("apex summary reports zero tests ran")
  bad_tests = []
  for test in result.get("tests", []) if isinstance(result.get("tests"), list) else []:
    outcome = test.get("outcome") if isinstance(test, dict) else None
    if outcome != "Pass":
      name = test.get("fullName", test.get("methodName", "unknown")) if isinstance(test, dict) else "unknown"
      bad_tests.append("%s:%s" % (name, outcome))
  if summary.get("outcome") == "Failed" or failing != 0 or bad_tests:
    detail = ("; ".join(bad_tests[:5])) or ("failing=%s" % failing)
    return fail("apex failures: %s (run %s)" % (detail, summary.get("testRunId", "unknown")))
  print("apex run=%s tests=%s passing=%s failing=0 skipped=%s" % (
    summary.get("testRunId"), tests_ran, summary.get("passing"), summary.get("skipped")))
  return 0


def cmd_agent_validate(args):
  if len(args) != 1:
    return fail("usage: agent-validate <file>")
  data = load(args[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or result.get("success") is not True:
    errors = ""
    if isinstance(result, dict) and result.get("errors"):
      errors = ": " + "; ".join(str(e) for e in result["errors"][:5])
    return fail("authoring bundle validation failed%s" % errors)
  print("agent-validate success")
  return 0


def cmd_agent_publish(args):
  if len(args) != 1:
    return fail("usage: agent-publish <file>")
  data = load(args[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or result.get("success") is not True:
    errors = ""
    if isinstance(result, dict) and result.get("errors"):
      errors = ": " + "; ".join(str(e) for e in result["errors"][:5])
    return fail("agent publish failed%s" % errors)
  print("agent-publish bot=%s" % result.get("botDeveloperName", "unknown"))
  return 0


def cmd_agent_activate(args):
  expect = None
  rest = []
  it = iter(args)
  for arg in it:
    if arg == "--expect-version":
      try:
        expect = next(it)
      except StopIteration:
        return fail("agent-activate needs a value after --expect-version")
    else:
      rest.append(arg)
  if len(rest) != 1:
    return fail("usage: agent-activate <file> [--expect-version N]")
  data = load(rest[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or result.get("success") is not True:
    return fail("agent activate failed")
  version = str(result.get("version", ""))
  if expect is not None and version != str(expect):
    return fail("activated version %s does not match expected %s" % (version, expect))
  print("agent-activate version=%s" % version)
  return 0


def cmd_agent_test_create(args):
  if len(args) != 1:
    return fail("usage: agent-test-create <file>")
  data = load(args[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or not result.get("path"):
    return fail("agent test create returned no metadata path")
  print("agent-test-create path=%s" % result.get("path"))
  return 0


def cmd_agent_test_run(args):
  if len(args) != 1:
    return fail("usage: agent-test-run <file>")
  data = load(args[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict):
    return fail("agent test run output has no result object")
  status = str(result.get("status", "")).upper()
  run_id = result.get("runId", "")
  if status != "COMPLETED":
    return fail("agent test run status is %s, not COMPLETED (run %s); resume it" % (
      status or "missing", run_id or "unknown"))
  if not run_id:
    return fail("agent test run has no run id")
  print("agent-test-run id=%s" % run_id)
  return 0


def cmd_publish_diff(args):
  if len(args) != 2:
    return fail("usage: publish-diff <before-listing> <after-listing>")
  try:
    before = set(Path(args[0]).read_text().split())
    after = set(Path(args[1]).read_text().split())
  except Exception as exc:
    return fail("cannot read version listings: %s" % exc)
  import re
  def versions(names):
    found = set()
    for token in names:
      match = re.match(r"v(\d+)\b", token)
      if match:
        found.add(int(match.group(1)))
    return found
  new_versions = sorted(versions(after) - versions(before))
  if len(new_versions) != 1:
    found = ", ".join("v%d" % n for n in new_versions) or "none"
    return fail("expected exactly one new published version, found: %s" % found)
  print("v%d" % new_versions[0])
  return 0


def cmd_preview_start(args):
  expect_agent = None
  rest = []
  it = iter(args)
  for arg in it:
    if arg == "--expect-agent":
      try:
        expect_agent = next(it)
      except StopIteration:
        return fail("preview-start needs a value after --expect-agent")
    else:
      rest.append(arg)
  if len(rest) != 1:
    return fail("usage: preview-start <file> [--expect-agent NAME]")
  data = load(rest[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or not result.get("sessionId"):
    return fail("preview start returned no session id")
  if expect_agent is not None and result.get("agentApiName") != expect_agent:
    return fail("preview session agent %s does not match expected %s" % (
      result.get("agentApiName"), expect_agent))
  print(result["sessionId"])
  return 0


def cmd_preview_send(args):
  expect_session = None
  rest = []
  it = iter(args)
  for arg in it:
    if arg == "--expect-session":
      try:
        expect_session = next(it)
      except StopIteration:
        return fail("preview-send needs a value after --expect-session")
    else:
      rest.append(arg)
  if len(rest) != 1:
    return fail("usage: preview-send <file> [--expect-session ID]")
  data = load(rest[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or not isinstance(result.get("messages"), list):
    return fail("preview send returned no messages list")
  if not result["messages"]:
    return fail("preview send returned zero messages")
  if expect_session is not None and result.get("sessionId") != expect_session:
    return fail("preview response session %s does not match %s" % (
      result.get("sessionId"), expect_session))
  texts = [m.get("message", "") for m in result["messages"]
           if isinstance(m, dict) and m.get("role") == "agent"]
  print("preview-send messages=%d chars=%d" % (len(result["messages"]), sum(len(t) for t in texts)))
  return 0


PLATFORM_AGENT_PERMSETS = (
  "AgentforceServiceAgentBase",
  "AgentforceServiceAgentUser",
  "EinsteinGPTPromptTemplateUser",
)


def cmd_agent_user_create(args):
  if len(args) != 1:
    return fail("usage: agent-user-create <file>")
  data = load(args[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict):
    return fail("agent user output has no result object")
  username = result.get("username", "")
  user_id = result.get("userId", "")
  if not username or not user_id:
    return fail("agent user output lacks username or user id")
  errors = result.get("permissionSetErrors")
  if not isinstance(errors, list) or errors:
    return fail("agent user permission errors: %s" % (errors or "missing error list"))
  assigned = result.get("permissionSetsAssigned", [])
  missing = [p for p in PLATFORM_AGENT_PERMSETS if p not in assigned]
  if missing:
    return fail("agent user lacks platform permission sets: " + ", ".join(missing))
  print("agent-user username=%s id=%s" % (username, user_id))
  return 0


def cmd_user_query(args):
  expect_username = None
  expect_profile = None
  rest = []
  it = iter(args)
  for arg in it:
    if arg in ("--expect-username", "--expect-profile"):
      try:
        value = next(it)
      except StopIteration:
        return fail("user-query needs a value after " + arg)
      if arg == "--expect-username":
        expect_username = value
      else:
        expect_profile = value
    else:
      rest.append(arg)
  if len(rest) != 1 or not expect_username or not expect_profile:
    return fail("usage: user-query <file> --expect-username U --expect-profile P")
  data = load(rest[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or not isinstance(result.get("records"), list):
    return fail("user query output has no records list")
  if result.get("totalSize") != 1 or len(result["records"]) != 1:
    return fail("expected exactly one user %s, found %s" % (expect_username, result.get("totalSize")))
  record = result["records"][0]
  if not isinstance(record, dict) or record.get("Username") != expect_username:
    return fail("user query returned an unexpected record")
  if record.get("IsActive") is not True:
    return fail("user %s is not active" % expect_username)
  profile = record.get("Profile", {}) if isinstance(record.get("Profile"), dict) else {}
  if profile.get("Name") != expect_profile:
    return fail("user %s has profile %s, expected %s" % (
      expect_username, profile.get("Name", "unknown"), expect_profile))
  print("user-query id=%s username=%s" % (record.get("Id", "unknown"), expect_username))
  return 0


def cmd_assignment_query(args):
  expected = []
  rest = []
  it = iter(args)
  for arg in it:
    if arg == "--expect":
      try:
        expected.append(next(it))
      except StopIteration:
        return fail("assignment-query needs a value after --expect")
    else:
      rest.append(arg)
  if len(rest) != 1 or not expected:
    return fail("usage: assignment-query <file> --expect NAME [--expect NAME...]")
  data = load(rest[0])
  if data is None:
    return 1
  result = unwrap(data)
  if not isinstance(result, dict) or not isinstance(result.get("records"), list):
    return fail("assignment query output has no records list")
  found = set()
  for record in result["records"]:
    permset = record.get("PermissionSet", {}) if isinstance(record, dict) else {}
    if isinstance(permset, dict) and permset.get("Name"):
      found.add(permset["Name"])
  missing = [name for name in expected if name not in found]
  if missing:
    return fail("missing permission set assignments: " + ", ".join(missing))
  print("assignment-query found=%s" % ",".join(sorted(found)))
  return 0


def cmd_json(args):
  if len(args) != 1:
    return fail("usage: json <file>")
  data = load(args[0])
  if data is None:
    return 1
  if isinstance(data, dict) and data.get("status") == 0:
    print("json status=0")
    return 0
  return fail("json envelope does not report status zero")


COMMANDS = {
  "deploy": cmd_deploy,
  "apex": cmd_apex,
  "agent-validate": cmd_agent_validate,
  "agent-publish": cmd_agent_publish,
  "agent-activate": cmd_agent_activate,
  "agent-test-create": cmd_agent_test_create,
  "agent-test-run": cmd_agent_test_run,
  "preview-start": cmd_preview_start,
  "preview-send": cmd_preview_send,
  "agent-user-create": cmd_agent_user_create,
  "user-query": cmd_user_query,
  "assignment-query": cmd_assignment_query,
  "publish-diff": cmd_publish_diff,
  "json": cmd_json,
}


def main(argv):
  if len(argv) < 2 or argv[0] not in COMMANDS:
    print("usage: verify_sf_output.py <%s> ..." % "|".join(sorted(COMMANDS)), file=sys.stderr)
    return 2
  return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
