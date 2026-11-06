#!/bin/sh
# Create the Service Triage agent test from committed scenarios.
# Deterministic: convert, verify topic and action names against published
# metadata, create the test, optionally run it and score results.
#
# Prerequisites: candidate revision deployed, agent published, and the
# publish retrieval present locally (GenAi metadata under force-app).
# For legacy tests the run exercises the activated agent version, so
# activate the candidate version first and pass it as AGENT_VERSION.
#
# Usage:
#   ORG_ALIAS=my-org AGENT_VERSION=2 sh scripts/create-service-triage-test.sh
#   ORG_ALIAS=my-org AGENT_VERSION=2 RUN_TEST=1 sh scripts/create-service-triage-test.sh
set -e

ALIAS="${ORG_ALIAS:?Set ORG_ALIAS to the target org alias first.}"
AGENT_VERSION="${AGENT_VERSION:?Set AGENT_VERSION to the published candidate version first.}"
TEST_API_NAME="${TEST_API_NAME:-Service_Triage_Agent_Test}"
SPEC="${SPEC:-specs/Service_Triage_Agent-testSpec.yaml}"
MAP="${MAP:-specs/Service_Triage_Agent-testMap.json}"
SUBJECT="${SUBJECT_NAME:-Service_Triage_Agent}"

echo "Step 1 of 4: convert committed scenarios to a test spec"
python3 tests/eval/convert_service_scenarios.py --out-spec "$SPEC" --out-map "$MAP" --subject-name "$SUBJECT"

echo "Step 2 of 4: verify expected topics and actions against local published metadata"
if ! ls force-app/main/default/genAiPlugins/*.xml >/dev/null 2>&1; then
  echo "WARNING: no GenAiPlugin metadata found locally. Publish must retrieve before topics can be verified."
  echo "Continuing with subagent developer names; confirm expectedTopic values after publish retrieval."
else
  echo "Local GenAiPlugin files:"
  ls force-app/main/default/genAiPlugins/*.xml
  echo "If expectedTopic values in $SPEC do not match these DeveloperNames, update the spec and rerun."
fi

echo "Step 3 of 4: create test $TEST_API_NAME in org $ALIAS"
sf agent test create --spec "$SPEC" --api-name "$TEST_API_NAME" --force-overwrite -o "$ALIAS" --json | tee "test-create-$TEST_API_NAME.json"

if [ "${RUN_TEST:-0}" = "1" ]; then
  echo "Step 4 of 4: run test and score against thresholds"
  mkdir -p agent-results
  sf agent test run -n "$TEST_API_NAME" -o "$ALIAS" -w 10 --result-format json -d agent-results --json | tee "test-run-$TEST_API_NAME.json"
  python3 tests/eval/check_agent_results.py --results agent-results --map "$MAP" \
    --commit "$(git rev-parse HEAD)" --agent-version "$AGENT_VERSION" --run-id "$TEST_API_NAME"
else
  echo "Step 4 of 4: run skipped (set RUN_TEST=1 to run and score)"
  echo "Run manually with:"
  echo "  sf agent test run -n $TEST_API_NAME -o $ALIAS -w 10 --result-format json -d agent-results"
  echo "then score with:"
  echo "  python3 tests/eval/check_agent_results.py --results agent-results --commit <sha> --agent-version $AGENT_VERSION"
fi

echo "Done. Candidate commit: $(git rev-parse HEAD 2>/dev/null || echo unknown). Agent version: $AGENT_VERSION."
