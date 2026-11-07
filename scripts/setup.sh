#!/usr/bin/env bash
# Full project setup: scratch org, deploy everything, run all local Apex tests.
# Non-idempotent step: org creation fails if the alias exists.
# Delete the old org first (sf org delete scratch -o <alias>) or pick a new alias.
# Every Salesforce step is verified from its JSON output. Unfinished async
# work fails explicitly instead of passing silently.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/sf_steps.sh
source "$SCRIPT_DIR/lib/sf_steps.sh"

DEV_HUB="${DEV_HUB:?Set DEV_HUB to your Dev Hub alias first. Example: DEV_HUB=my-hub bash scripts/setup.sh}"
ALIAS="${ORG_ALIAS:-foundry}"

echo "Step 1 of 3: create scratch org $ALIAS"
run_step "create scratch org $ALIAS" "scratch-create-$ALIAS.json" \
  sf org create scratch -v "$DEV_HUB" -f config/project-scratch-def.json -a "$ALIAS" -y 7 -w 10 -d --json
verify_step json "scratch-create-$ALIAS.json"

echo "Step 2 of 3: deploy all source"
run_step "deploy all source" "deploy-all-$ALIAS.json" \
  sf project deploy start -o "$ALIAS" -w 10 --json
verify_step deploy "deploy-all-$ALIAS.json"

echo "Step 3 of 3: run local Apex tests"
run_step "run local Apex tests" "apex-local-$ALIAS.json" \
  sf apex run test -o "$ALIAS" -l RunLocalTests -r human -w 10 --json
verify_step apex "apex-local-$ALIAS.json"
echo "Note: this deploys metadata only. It does not validate, publish, or activate any agent version."
echo "Use scripts/setup-service-triage.sh for the supported agent lifecycle."
echo "Done. Org alias: $ALIAS"
