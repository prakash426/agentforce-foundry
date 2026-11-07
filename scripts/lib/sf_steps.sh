# Shared helpers for Foundry org scripts. Source from bash only.
# Requires: bash, set -euo pipefail in the caller, python3 for verification.
# shellcheck shell=bash

# Run a command, keep full output in a file, echo it, and propagate failures.
# Usage: run_step "<description>" <output-file> <command...>
# Returns the command exit status; with set -e a failure stops the script.
run_step() {
  local desc=$1
  local out=$2
  shift 2
  echo "--- $desc ---"
  set +e
  "$@" >"$out" 2>&1
  local status=$?
  set -e
  cat "$out"
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
