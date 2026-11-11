# Shared helpers for Foundry org scripts. Source from bash only.
# Requires: bash, set -euo pipefail in the caller, python3 for verification.
# shellcheck shell=bash

# Run a command, keep stdout in a file, echo everything, propagate failures.
# Stdout goes to <output-file> so it stays parseable JSON; stderr goes to
# <output-file>.err so CLI warnings (update notices, auth hints) never
# pollute the payload the verifier reads. Both print to the terminal.
# Usage: run_step "<description>" <output-file> <command...>
# Returns the command exit status; with set -e a failure stops the script.
run_step() {
  local desc=$1
  local out=$2
  shift 2
  echo "--- $desc ---"
  set +e
  "$@" >"$out" 2>"$out.err"
  local status=$?
  set -e
  cat "$out" "$out.err"
  if [ "$status" -ne 0 ]; then
    echo "FAILED: $desc (exit $status). Output kept in $out." >&2
    return "$status"
  fi
  return 0
}

# Verify a CLI JSON document with the shared verifier. Stops on failure.
# Usage: verify_step "<subcommand>" <file> [extra verifier args...]
verify_step() {
  local sub=$1
  shift
  python3 scripts/verify_sf_output.py "$sub" "$@"
}

# Fail early when the installed CLI predates a required command.
# Probes "sf <command> --help" for each listed command and stops with
# update guidance when any probe fails, before any org mutation runs.
# Usage: require_sf_commands "agent validate authoring-bundle" ...
require_sf_commands() {
  local missing=""
  local cmd
  for cmd in "$@"; do
    # shellcheck disable=SC2086
    if ! sf $cmd --help >/dev/null 2>&1; then
      missing="$missing
  sf $cmd"
    fi
  done
  if [ -n "$missing" ]; then
    echo "This script needs Salesforce CLI commands that are missing:$missing" >&2
    echo "Update to @salesforce/cli@2.157.8 or newer (the pinned CI version), then rerun." >&2
    return 1
  fi
}
