#!/usr/bin/env bash
# Create the Service Triage agent test from committed scenarios.
# Deterministic: convert, resolve names against published metadata,
# create the test, optionally run it and score results.
#
# Prerequisites: candidate revision deployed, agent published, and the
# publish retrieval present locally (GenAi metadata under force-app).
# For legacy tests the run exercises the activated agent version, so
# activate the candidate version first and pass it as AGENT_VERSION.
# The script verifies a matching local BotVersion file exists; the
# binding is recorded as operator asserted, because legacy results do
# not expose the tested version. See the evaluation record limitation.
#
# Usage:
#   ORG_ALIAS=my-org AGENT_VERSION=2 bash scripts/create-service-triage-test.sh
#   ORG_ALIAS=my-org AGENT_VERSION=2 RUN_TEST=1 bash scripts/create-service-triage-test.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/sf_steps.sh
source "$SCRIPT_DIR/lib/sf_steps.sh"

ALIAS="${ORG_ALIAS:?Set ORG_ALIAS to the target org alias first.}"
AGENT_VERSION="${AGENT_VERSION:?Set AGENT_VERSION to the published candidate version first.}"
TEST_API_NAME="${TEST_API_NAME:-Service_Triage_Agent_Test}"
SPEC="${SPEC:-specs/Service_Triage_Agent-testSpec.yaml}"
MAP="${MAP:-specs/Service_Triage_Agent-testMap.json}"
RESOLVED_SPEC="${RESOLVED_SPEC:-specs/Service_Triage_Agent-testSpec.resolved.yaml}"
RESOLVE_REPORT="${RESOLVE_REPORT:-specs/Service_Triage_Agent-resolve.json}"
SUBJECT="${SUBJECT_NAME:-Service_Triage_Agent}"

echo "Step 1 of 5: convert committed scenarios to a test spec"
python3 tests/eval/convert_service_scenarios.py --out-spec "$SPEC" --out-map "$MAP" --subject-name "$SUBJECT"

echo "Step 2 of 5: resolve expected topics and actions against published metadata"
python3 tests/eval/resolve_eval_metadata.py --spec "$SPEC" --map "$MAP" \
  --project-root . --out-spec "$RESOLVED_SPEC" --report "$RESOLVE_REPORT" --agent "$SUBJECT"

echo "Step 3 of 5: confirm candidate version $AGENT_VERSION exists locally"
VERSION_NUM="$(echo "$AGENT_VERSION" | sed 's/^v//')"
if ! ls "force-app/main/default/bots/$SUBJECT/v$VERSION_NUM.botVersion-meta.xml" >/dev/null 2>&1; then
  echo "No local BotVersion file for $SUBJECT version $AGENT_VERSION. Publish must retrieve first." >&2
  exit 1
fi
echo "Found local BotVersion for $SUBJECT version $AGENT_VERSION (operator asserts it is the active one)."

echo "Step 4 of 5: create test $TEST_API_NAME in org $ALIAS"
run_step "create agent test" "test-create-$TEST_API_NAME.json" \
  sf agent test create --spec "$RESOLVED_SPEC" --api-name "$TEST_API_NAME" --force-overwrite -o "$ALIAS" --json
verify_step agent-test-create "test-create-$TEST_API_NAME.json"

if [ "${RUN_TEST:-0}" = "1" ]; then
  echo "Step 5 of 5: run test and score against thresholds"
  mkdir -p agent-results
  run_step "run agent test" "test-run-$TEST_API_NAME.json" \
    sf agent test run -n "$TEST_API_NAME" -o "$ALIAS" -w 10 --result-format json -d agent-results --json
  RUN_LINE="$(verify_step agent-test-run "test-run-$TEST_API_NAME.json")"
  echo "$RUN_LINE"
  RUN_ID="$(echo "$RUN_LINE" | sed -n 's/^agent-test-run id=//p')"
  if [ -z "$RUN_ID" ]; then
    echo "Could not determine the evaluation run id from test output." >&2
    exit 1
  fi
  python3 tests/eval/check_agent_results.py --results agent-results --map "$MAP" \
    --commit "$(git rev-parse HEAD)" --agent-version "$AGENT_VERSION" --run-id "$RUN_ID"
else
  echo "Step 5 of 5: run skipped (set RUN_TEST=1 to run and score)"
  echo "Run manually with:"
  echo "  sf agent test run -n $TEST_API_NAME -o $ALIAS -w 10 --result-format json -d agent-results --json"
  echo "then score with:"
  echo "  python3 tests/eval/check_agent_results.py --results agent-results --commit <sha> --agent-version $AGENT_VERSION --run-id <runId>"
fi

echo "Done. Candidate commit: $(git rev-parse HEAD 2>/dev/null || echo unknown). Agent version: $AGENT_VERSION."
