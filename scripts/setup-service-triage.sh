#!/usr/bin/env bash
# Service Triage setup: org, dependencies, validate, publish, tests.
# Supported lifecycle: deploy Apex plus permission sets, validate the
# authoring bundle, publish a candidate agent version, then activate
# separately. Metadata deployment alone never creates a published
# executable agent version. Activation stays manual unless ACTIVATE=1.
#
# Usage with a fresh scratch org:
#   DEV_HUB=my-hub bash scripts/setup-service-triage.sh
# Usage with an existing eligible dev org (Agentforce enabled):
#   USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org bash scripts/setup-service-triage.sh
# With an agent user for publish (recommended):
#   DEV_HUB=my-hub AGENT_USER=agent.user@example.com bash scripts/setup-service-triage.sh
# To also activate the published version (explicit opt in):
#   DEV_HUB=my-hub AGENT_USER=a@b.c ACTIVATE=1 bash scripts/setup-service-triage.sh
#
# The committed .agent file holds an UPDATE_WITH_DEFAULT_AGENT_USER
# placeholder. When AGENT_USER is set, this script swaps it in a
# temporary working copy for publish only, then restores the file so
# no org specific value is committed. Restoration runs on success,
# failure, and interruption via trap. Without AGENT_USER the script
# warns and continues; publish may fail until a real user is set in
# Agentforce Studio after the first publish attempt.
#
# Every Salesforce step is verified from its JSON output, not from
# exit codes or file presence alone. Unfinished async work fails
# explicitly instead of passing silently.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/sf_steps.sh
source "$SCRIPT_DIR/lib/sf_steps.sh"

ALIAS="${ORG_ALIAS:-foundry-triage}"
AGENT_API_NAME="Service_Triage_Agent"
AGENT_FILE="force-app/main/default/aiAuthoringBundles/Service_Triage_Agent/Service_Triage_Agent.agent"
PLACEHOLDER="UPDATE_WITH_DEFAULT_AGENT_USER"
AGENT_BACKUP=""

restore_agent_file() {
  if [ -n "${AGENT_BACKUP:-}" ] && [ -f "$AGENT_BACKUP" ]; then
    cp "$AGENT_BACKUP" "$AGENT_FILE"
    rm -f "$AGENT_BACKUP"
    AGENT_BACKUP=""
    echo "Restored $AGENT_FILE to committed placeholder state."
  fi
}
trap restore_agent_file EXIT INT TERM

if [ "${USE_EXISTING_ORG:-0}" = "1" ]; then
  echo "Step 1 of 7: using existing org $ALIAS (no scratch create)"
  run_step "show org $ALIAS" "org-display-$ALIAS.json" sf org display -o "$ALIAS" --json
  verify_step json "org-display-$ALIAS.json"
else
  DEV_HUB="${DEV_HUB:?Set DEV_HUB to your Dev Hub alias first. Example: DEV_HUB=my-hub bash scripts/setup-service-triage.sh (or USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org to reuse an org)}"
  echo "Step 1 of 7: create scratch org $ALIAS"
  echo "Non-idempotent: fails if the alias exists. Delete the old org or export a new ORG_ALIAS."
  run_step "create scratch org $ALIAS" "scratch-create-$ALIAS.json" \
    sf org create scratch -v "$DEV_HUB" -f config/project-scratch-def.json -a "$ALIAS" -y 7 -w 10 -d --json
  verify_step json "scratch-create-$ALIAS.json"
fi

echo "Step 2 of 7: deploy Service Triage dependencies (Apex plus permission sets)"
run_step "deploy dependencies" "deploy-deps-$ALIAS.json" \
  sf project deploy start -o "$ALIAS" -d force-app/main/default/classes -d force-app/main/default/permissionsets -w 10 --json
verify_step deploy "deploy-deps-$ALIAS.json"

echo "Step 3 of 7: assign Foundry Service permission set to the admin user"
run_step "assign permission set" "permset-$ALIAS.json" \
  sf org assign permset -n Agentforce_Foundry_Service -o "$ALIAS" --json
verify_step json "permset-$ALIAS.json"

if [ -n "${AGENT_USER:-}" ]; then
  echo "Resolving agent user placeholder for this publish only (restored afterward)"
  AGENT_BACKUP="$(mktemp /tmp/service-triage-agent.XXXXXX)"
  cp "$AGENT_FILE" "$AGENT_BACKUP"
  sed "s/$PLACEHOLDER/$AGENT_USER/" "$AGENT_BACKUP" > "$AGENT_FILE"
else
  echo "WARNING: AGENT_USER is not set. The bundle still holds $PLACEHOLDER."
  echo "Validation runs anyway. Publish may fail until a real default agent user is set."
fi

echo "Step 4 of 7: validate the authoring bundle (compile check, no publish)"
run_step "validate authoring bundle" "validate-$AGENT_API_NAME.json" \
  sf agent validate authoring-bundle -n "$AGENT_API_NAME" -o "$ALIAS" --json
verify_step agent-validate "validate-$AGENT_API_NAME.json"

echo "Step 5 of 7: publish a candidate agent version (stays inactive until activated)"
ls "force-app/main/default/bots/$AGENT_API_NAME" > "publish-before-$AGENT_API_NAME.txt" 2>/dev/null || true
run_step "publish authoring bundle" "publish-$AGENT_API_NAME.json" \
  sf agent publish authoring-bundle -n "$AGENT_API_NAME" -o "$ALIAS" --json
verify_step agent-publish "publish-$AGENT_API_NAME.json"
ls "force-app/main/default/bots/$AGENT_API_NAME" > "publish-after-$AGENT_API_NAME.txt"
CANDIDATE_VERSION="$(verify_step publish-diff "publish-before-$AGENT_API_NAME.txt" "publish-after-$AGENT_API_NAME.txt")"
echo "Candidate agent version: $CANDIDATE_VERSION"
echo "$CANDIDATE_VERSION" > "candidate-version-$AGENT_API_NAME.txt"

restore_agent_file

echo "Step 6 of 7: run Service Triage Apex tests against installed code"
mkdir -p ci-results
run_step "run Service Apex tests" ci-results/apex-run.json \
  sf apex run test -o "$ALIAS" -n ServiceTriageActionTest -r junit -d ci-results -w 10 -c --json
verify_step apex ci-results/apex-run.json
echo "Apex results kept under ci-results."

if [ "${ACTIVATE:-0}" = "1" ]; then
  if [ -z "${AGENT_VERSION:-}" ]; then
    echo "ACTIVATE=1 needs AGENT_VERSION (the published version number). Example: AGENT_VERSION=2 ACTIVATE=1 ..."
    exit 1
  fi
  echo "Step 7 of 7: activating agent version $AGENT_VERSION (explicit opt in)"
  run_step "activate agent" "activate-$AGENT_API_NAME-v$AGENT_VERSION.json" \
    sf agent activate -n "$AGENT_API_NAME" --version "$AGENT_VERSION" -o "$ALIAS" --json
  verify_step agent-activate "activate-$AGENT_API_NAME-v$AGENT_VERSION.json" --expect-version "$AGENT_VERSION"
  echo "Next: preview with: sf agent preview -n $AGENT_API_NAME -o $ALIAS --use-live-actions"
else
  echo "Step 7 of 7: activation is pending by design (see kit README manual section)"
  echo "Next: set the default agent user on $AGENT_API_NAME in Agentforce Studio if not set via AGENT_USER,"
  echo "then activate the published candidate $CANDIDATE_VERSION, for example:"
  echo "  sf agent activate -n $AGENT_API_NAME --version <N> -o $ALIAS"
  echo "then preview with: sf agent preview -n $AGENT_API_NAME -o $ALIAS --use-live-actions"
fi

echo "Done. Org alias: $ALIAS"
echo "Candidate commit: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "Candidate agent version: $CANDIDATE_VERSION"
