#!/bin/sh
# Service Triage setup: org, dependencies, validate, publish, tests.
# Supported lifecycle: deploy Apex plus permission sets, validate the
# authoring bundle, publish a candidate agent version, then activate
# separately. Metadata deployment alone never creates a published
# executable agent version. Activation stays manual unless ACTIVATE=1.
#
# Usage with a fresh scratch org:
#   DEV_HUB=my-hub sh scripts/setup-service-triage.sh
# Usage with an existing eligible dev org (Agentforce enabled):
#   USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org sh scripts/setup-service-triage.sh
# With an agent user for publish (recommended):
#   DEV_HUB=my-hub AGENT_USER=agent.user@example.com sh scripts/setup-service-triage.sh
# To also activate the published version (explicit opt in):
#   DEV_HUB=my-hub AGENT_USER=a@b.c ACTIVATE=1 sh scripts/setup-service-triage.sh
#
# The committed .agent file holds an UPDATE_WITH_DEFAULT_AGENT_USER
# placeholder. When AGENT_USER is set, this script swaps it in a
# temporary working copy for publish only, then restores the file so
# no org specific value is committed. Without AGENT_USER the script
# warns and continues; publish may fail until a real user is set in
# Agentforce Studio after the first publish attempt.
set -e

ALIAS="${ORG_ALIAS:-foundry-triage}"
AGENT_API_NAME="Service_Triage_Agent"
AGENT_FILE="force-app/main/default/aiAuthoringBundles/Service_Triage_Agent/Service_Triage_Agent.agent"
PLACEHOLDER="UPDATE_WITH_DEFAULT_AGENT_USER"

restore_agent_file() {
  if [ -n "$AGENT_BACKUP" ] && [ -f "$AGENT_BACKUP" ]; then
    cp "$AGENT_BACKUP" "$AGENT_FILE"
    rm -f "$AGENT_BACKUP"
    echo "Restored $AGENT_FILE to committed placeholder state."
  fi
}

if [ "${USE_EXISTING_ORG:-0}" = "1" ]; then
  echo "Step 1 of 7: using existing org $ALIAS (no scratch create)"
  sf org display -o "$ALIAS" --json > "org-display-$ALIAS.json"
else
  DEV_HUB="${DEV_HUB:?Set DEV_HUB to your Dev Hub alias first. Example: DEV_HUB=my-hub sh scripts/setup-service-triage.sh (or USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org to reuse an org)}"
  echo "Step 1 of 7: create scratch org $ALIAS"
  echo "Non-idempotent: fails if the alias exists. Delete the old org or export a new ORG_ALIAS."
  sf org create scratch -v "$DEV_HUB" -f config/project-scratch-def.json -a "$ALIAS" -y 7 -w 10 -d
fi

echo "Step 2 of 7: deploy Service Triage dependencies (Apex plus permission sets)"
sf project deploy start -o "$ALIAS" -d force-app/main/default/classes -d force-app/main/default/permissionsets -w 10

echo "Step 3 of 7: assign Foundry Service permission set to the admin user"
sf org assign permset -n Agentforce_Foundry_Service -o "$ALIAS"

if [ -n "${AGENT_USER:-}" ]; then
  echo "Resolving agent user placeholder for this publish only (restored afterward)"
  AGENT_BACKUP="$(mktemp /tmp/service-triage-agent.XXXXXX)"
  cp "$AGENT_FILE" "$AGENT_BACKUP"
  trap restore_agent_file EXIT INT TERM
  sed "s/$PLACEHOLDER/$AGENT_USER/" "$AGENT_BACKUP" > "$AGENT_FILE"
else
  echo "WARNING: AGENT_USER is not set. The bundle still holds $PLACEHOLDER."
  echo "Validation runs anyway. Publish may fail until a real default agent user is set."
fi

echo "Step 4 of 7: validate the authoring bundle (compile check, no publish)"
sf agent validate authoring-bundle -n "$AGENT_API_NAME" -o "$ALIAS" --json | tee "validate-$AGENT_API_NAME.json"

echo "Step 5 of 7: publish a candidate agent version (stays inactive until activated)"
sf agent publish authoring-bundle -n "$AGENT_API_NAME" -o "$ALIAS" --json | tee "publish-$AGENT_API_NAME.json"
echo "Published metadata was retrieved back to this project by the CLI unless skipped."
echo "Find the candidate version under force-app/main/default/bots/$AGENT_API_NAME/vN.botVersion-meta.xml"

restore_agent_file
trap - EXIT INT TERM

echo "Step 6 of 7: run Service Triage Apex tests against installed code"
mkdir -p ci-results
sf apex run test -o "$ALIAS" -n ServiceTriageActionTest -r junit -d ci-results -w 10 -c
echo "Apex results kept under ci-results."

if [ "${ACTIVATE:-0}" = "1" ]; then
  if [ -z "${AGENT_VERSION:-}" ]; then
    echo "ACTIVATE=1 needs AGENT_VERSION (the published version number). Example: AGENT_VERSION=1 ACTIVATE=1 ..."
    exit 1
  fi
  echo "Step 7 of 7: activating agent version $AGENT_VERSION (explicit opt in)"
  sf agent activate -n "$AGENT_API_NAME" --version "$AGENT_VERSION" -o "$ALIAS" --json | tee "activate-$AGENT_API_NAME-v$AGENT_VERSION.json"
  echo "Next: preview with: sf agent preview -n $AGENT_API_NAME -o $ALIAS --use-live-actions"
else
  echo "Step 7 of 7: activation is pending by design (see kit README manual section)"
  echo "Next: set the default agent user on $AGENT_API_NAME in Agentforce Studio if not set via AGENT_USER,"
  echo "then activate a published version, for example:"
  echo "  sf agent activate -n $AGENT_API_NAME --version <N> -o $ALIAS"
  echo "then preview with: sf agent preview -n $AGENT_API_NAME -o $ALIAS --use-live-actions"
fi

echo "Done. Org alias: $ALIAS"
echo "Candidate commit: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
