#!/bin/sh
# Service Triage setup: scratch org, deploy, permission set, Apex tests.
# Non-idempotent step: org creation fails if the alias already exists.
# Delete the old org first (sf org delete scratch -o <alias>) or pick a new alias.
# Every step below was checked against local sf 2.145.6 help text.
# Long flags appear only where the command offers no short form.
set -e

DEV_HUB="${DEV_HUB:?Set DEV_HUB to your Dev Hub alias first. Example: DEV_HUB=my-hub sh scripts/setup-service-triage.sh}"
ALIAS="${ORG_ALIAS:-foundry-triage}"

echo "Step 1 of 5: create scratch org $ALIAS"
sf org create scratch -v "$DEV_HUB" -f config/project-scratch-def.json -a "$ALIAS" -y 7 -w 10 -d

echo "Step 2 of 5: deploy Service Triage source"
sf project deploy start -o "$ALIAS" -d force-app/main/default/classes -d force-app/main/default/permissionsets -d force-app/main/default/aiAuthoringBundles -w 10

echo "Step 3 of 5: assign Foundry Service permission set to the admin user"
sf org assign permset -n Agentforce_Foundry_Service -o "$ALIAS"

echo "Step 4 of 5: run Service Triage Apex tests"
sf apex run test -o "$ALIAS" -n ServiceTriageActionTest -r human -w 10

echo "Step 5 of 5: agent activation is manual (see kits/service-triage/README.md)"
echo "Next: set the default agent user on Service_Triage_Agent, activate the agent,"
echo "then generate a test spec with: sf agent generate test-spec -f specs/Service_Triage-testSpec.yaml"
echo "Done. Org alias: $ALIAS"
