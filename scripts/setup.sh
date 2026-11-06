#!/bin/sh
# Full project setup: scratch org, deploy everything, run all local Apex tests.
# Non-idempotent step: org creation fails if the alias already exists.
# Delete the old org first (sf org delete scratch -o <alias>) or pick a new alias.
set -e

DEV_HUB="${DEV_HUB:?Set DEV_HUB to your Dev Hub alias first. Example: DEV_HUB=my-hub sh scripts/setup.sh}"
ALIAS="${ORG_ALIAS:-foundry}"

echo "Step 1 of 3: create scratch org $ALIAS"
sf org create scratch -v "$DEV_HUB" -f config/project-scratch-def.json -a "$ALIAS" -y 7 -w 10 -d

echo "Step 2 of 3: deploy all source"
sf project deploy start -o "$ALIAS" -w 10

echo "Step 3 of 3: run local Apex tests"
sf apex run test -o "$ALIAS" -l RunLocalTests -r human -w 10
echo "Done. Org alias: $ALIAS"
