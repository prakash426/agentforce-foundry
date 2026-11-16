#!/usr/bin/env bash
# Validate the Service Triage authoring bundle without publishing.
# Validation only: compiles the Agent Script server side and stops.
# Nothing is published, activated, deployed, or executed.
#
# Usage with an explicit runtime username:
#   ORG_ALIAS=my-org RUNTIME_USER=agent.user@example.com bash scripts/validate-service-triage.sh
# Usage with the username recorded by a prior setup run:
#   ORG_ALIAS=my-org bash scripts/validate-service-triage.sh
#
# The committed .agent file holds an UPDATE_WITH_DEFAULT_AGENT_USER
# placeholder inside the access block. This script substitutes the
# resolved username for validation only, then restores the original
# file from a backup, preserving any unrelated local edits. The
# backup is a plain file copy, never a checkout, and restoration
# runs on success, failure, and interruption via trap. If the
# placeholder is already absent, the script stops before contacting
# the org rather than validating a stale substitution.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/sf_steps.sh
source "$SCRIPT_DIR/lib/sf_steps.sh"

ALIAS="${ORG_ALIAS:?Set ORG_ALIAS to the target org alias first.}"
AGENT_API_NAME="Service_Triage_Agent"
AGENT_FILE="force-app/main/default/aiAuthoringBundles/Service_Triage_Agent/Service_Triage_Agent.agent"
PLACEHOLDER="UPDATE_WITH_DEFAULT_AGENT_USER"
AGENT_BACKUP=""

restore_agent_file() {
  if [ -n "${AGENT_BACKUP:-}" ] && [ -f "$AGENT_BACKUP" ]; then
    cp "$AGENT_BACKUP" "$AGENT_FILE"
    rm -f "$AGENT_BACKUP"
    AGENT_BACKUP=""
    echo "Restored $AGENT_FILE from backup."
  fi
}
trap restore_agent_file EXIT INT TERM

echo "Step 0 of 2: confirm the CLI ships authoring-bundle validation"
require_sf_commands "agent validate authoring-bundle"

if [ -n "${RUNTIME_USER:-}" ]; then
  USERNAME="$RUNTIME_USER"
  echo "Runtime user from RUNTIME_USER."
elif [ -f "agent-user-$ALIAS.json" ]; then
  USERNAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("username", ""))' "agent-user-$ALIAS.json")"
  echo "Runtime user from agent-user-$ALIAS.json."
else
  echo "Set RUNTIME_USER to the existing runtime username, or run setup first so agent-user-$ALIAS.json exists." >&2
  exit 1
fi
if [ -z "$USERNAME" ]; then
  echo "No runtime username resolved. Set RUNTIME_USER explicitly." >&2
  exit 1
fi

if ! grep -q "$PLACEHOLDER" "$AGENT_FILE"; then
  echo "Placeholder $PLACEHOLDER absent from $AGENT_FILE. Restore the committed placeholder before validating." >&2
  exit 1
fi

echo "Step 1 of 2: substitute the runtime username for validation only"
AGENT_BACKUP="$(mktemp /tmp/service-triage-validate.XXXXXX)"
cp "$AGENT_FILE" "$AGENT_BACKUP"
sed "s/$PLACEHOLDER/$USERNAME/" "$AGENT_BACKUP" > "$AGENT_FILE"
if grep -q "$PLACEHOLDER" "$AGENT_FILE"; then
  echo "Substitution did not replace the placeholder. Restoring and stopping." >&2
  exit 1
fi

echo "Step 2 of 2: validate the authoring bundle (compile check, no publish)"
run_step "validate authoring bundle" "validate-$AGENT_API_NAME.json" \
  sf agent validate authoring-bundle -n "$AGENT_API_NAME" -o "$ALIAS" --json
verify_step agent-validate "validate-$AGENT_API_NAME.json"

restore_agent_file
if ! grep -q "$PLACEHOLDER" "$AGENT_FILE"; then
  echo "Restoration check failed: $PLACEHOLDER missing from $AGENT_FILE." >&2
  exit 1
fi
echo "Validation passed and the placeholder is restored. Nothing was published."
