#!/usr/bin/env bash
# Establish the agent runtime user before validation and publishing.
# Creates a user with the supported CLI command when AGENT_USER is unset,
# or verifies an explicitly supplied existing user. Assigns the custom
# Service permission set to the runtime user and writes a record file.
# Fails early with guidance when prerequisites are absent. Never publishes.
#
# Usage (create in a fresh scratch org):
#   ORG_ALIAS=my-org bash scripts/setup-agent-user.sh
# Usage (verify an existing user in a development org):
#   ORG_ALIAS=my-org AGENT_USER=agent@example.com bash scripts/setup-agent-user.sh
# Optional base pattern for generated usernames:
#   ORG_ALIAS=my-org AGENT_BASE_USERNAME=service-agent@example.com bash scripts/setup-agent-user.sh
#
# Output: agent-user-<alias>.json with username, user id, mode, profile,
# and assigned permission sets. Prints the username on stdout for capture.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/sf_steps.sh
source "$SCRIPT_DIR/lib/sf_steps.sh"

ALIAS="${ORG_ALIAS:?Set ORG_ALIAS to the target org alias first.}"
CUSTOM_PERMSET="Agentforce_Foundry_Service"
REQUIRED_PROFILE="Einstein Agent User"
OUT="agent-user-$ALIAS.json"

soql_escape() {
  printf '%s' "$1" | sed "s/'/''/g"
}

query_assignments() {
  local username=$1
  local out=$2
  local escaped
  escaped="$(soql_escape "$username")"
  run_step "list assignments for $username" "$out" \
    sf data query -o "$ALIAS" \
    -q "SELECT PermissionSet.Name FROM PermissionSetAssignment WHERE Assignee.Username = '$escaped'" \
    --json
}

if [ -n "${AGENT_USER:-}" ]; then
  echo "Verifying existing agent user $AGENT_USER in org $ALIAS"
  ESCAPED="$(soql_escape "$AGENT_USER")"
  run_step "look up user $AGENT_USER" "agent-user-lookup-$ALIAS.json" \
    sf data query -o "$ALIAS" \
    -q "SELECT Id, Username, IsActive, Profile.Name FROM User WHERE Username = '$ESCAPED'" \
    --json
  verify_step user-query "agent-user-lookup-$ALIAS.json" \
    --expect-username "$AGENT_USER" --expect-profile "$REQUIRED_PROFILE"
  USER_ID="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["result"]["records"][0]["Id"])' "agent-user-lookup-$ALIAS.json")"
  query_assignments "$AGENT_USER" "agent-user-assign-$ALIAS.json"
  if ! verify_step assignment-query "agent-user-assign-$ALIAS.json" \
      --expect AgentforceServiceAgentBase \
      --expect AgentforceServiceAgentUser \
      --expect EinsteinGPTPromptTemplateUser; then
    echo "User $AGENT_USER lacks required platform permission sets." >&2
    echo "Assign them in Setup, or unset AGENT_USER to create a compliant user." >&2
    exit 1
  fi
  if verify_step assignment-query "agent-user-assign-$ALIAS.json" --expect "$CUSTOM_PERMSET" 2>/dev/null; then
    echo "Custom permission set $CUSTOM_PERMSET already assigned."
  else
    echo "Assigning $CUSTOM_PERMSET to $AGENT_USER"
    run_step "assign $CUSTOM_PERMSET" "agent-user-custom-$ALIAS.json" \
      sf org assign permset -n "$CUSTOM_PERMSET" -o "$ALIAS" -b "$AGENT_USER" --json
    verify_step json "agent-user-custom-$ALIAS.json"
    query_assignments "$AGENT_USER" "agent-user-assign-$ALIAS.json"
    verify_step assignment-query "agent-user-assign-$ALIAS.json" --expect "$CUSTOM_PERMSET"
  fi
  MODE="existing"
  USERNAME="$AGENT_USER"
else
  echo "Creating agent user in org $ALIAS"
  CREATE_ARGS=(sf org create agent-user -o "$ALIAS" --json)
  if [ -n "${AGENT_BASE_USERNAME:-}" ]; then
    CREATE_ARGS+=(--base-username "$AGENT_BASE_USERNAME")
  fi
  run_step "create agent user" "agent-user-create-$ALIAS.json" "${CREATE_ARGS[@]}"
  CREATE_LINE="$(verify_step agent-user-create "agent-user-create-$ALIAS.json")"
  echo "$CREATE_LINE"
  USERNAME="$(echo "$CREATE_LINE" | sed -n 's/^agent-user username=\([^ ]*\) .*$/\1/p')"
  USER_ID="$(echo "$CREATE_LINE" | sed -n 's/^agent-user username=[^ ]* id=\(.*\)$/\1/p')"
  if [ -z "$USERNAME" ] || [ -z "$USER_ID" ]; then
    echo "Could not capture the created username from CLI output." >&2
    exit 1
  fi
  echo "Assigning $CUSTOM_PERMSET to $USERNAME"
  run_step "assign $CUSTOM_PERMSET" "agent-user-custom-$ALIAS.json" \
    sf org assign permset -n "$CUSTOM_PERMSET" -o "$ALIAS" -b "$USERNAME" --json
  verify_step json "agent-user-custom-$ALIAS.json"
  query_assignments "$USERNAME" "agent-user-assign-$ALIAS.json"
  verify_step assignment-query "agent-user-assign-$ALIAS.json" \
    --expect AgentforceServiceAgentBase \
    --expect AgentforceServiceAgentUser \
    --expect EinsteinGPTPromptTemplateUser \
    --expect "$CUSTOM_PERMSET"
  MODE="created"
fi

python3 -c 'import json,sys; json.dump({"username": sys.argv[2], "userId": sys.argv[3], "mode": sys.argv[4], "profile": sys.argv[5], "customPermset": "Agentforce_Foundry_Service"}, open(sys.argv[1], "w"), indent=2)' \
  "$OUT" "$USERNAME" "$USER_ID" "$MODE" "$REQUIRED_PROFILE"
echo "Agent runtime user ready: $USERNAME (mode $MODE). Record kept in $OUT."
echo "AGENT_USERNAME=$USERNAME"
