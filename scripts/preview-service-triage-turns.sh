#!/usr/bin/env bash
# Sequential preview conversations for Service Triage.
# Sends each utterance in a turns file through one preview session per
# sequence, saving a full transcript. This exercises real multi-turn
# behavior: the agent produces every reply, unlike seeded history evals
# that only test the next response in supplied context.
#
# Usage:
#   ORG_ALIAS=my-org bash scripts/preview-service-triage-turns.sh
#   ORG_ALIAS=my-org TURNS=tests/fixtures/service-triage-turns.json SEQUENCE=help-to-triage bash scripts/preview-service-triage-turns.sh
# Preview a draft bundle instead of the published agent:
#   ORG_ALIAS=my-org TARGET=bundle ACTIONS=live bash scripts/preview-service-triage-turns.sh
#
# TARGET=published (default) previews the activated agent by api name.
# TARGET=bundle previews the local authoring bundle; ACTIONS must be
# live (real org actions) or simulate (AI mocked actions). ACTIONS is
# ignored for published agents. Action mode flags go only to session
# start, which is the single command that accepts them; every send and
# end carries the agent identity plus the session id.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/sf_steps.sh
source "$SCRIPT_DIR/lib/sf_steps.sh"

ALIAS="${ORG_ALIAS:?Set ORG_ALIAS to the target org alias first.}"
SUBJECT="${SUBJECT_NAME:-Service_Triage_Agent}"
TURNS="${TURNS:-tests/fixtures/service-triage-turns.json}"
SEQUENCE="${SEQUENCE:-}"
TARGET="${TARGET:-published}"
ACTIONS="${ACTIONS:-live}"
OUT_DIR="${OUT_DIR:-preview-transcripts}"
SESSION_ID=""
TURNS_FAILED=0
END_FAILED=0

case "$TARGET" in
  published|bundle) ;;
  *) echo "TARGET must be published or bundle, got: $TARGET" >&2; exit 1;;
esac
case "$ACTIONS" in
  live|simulate) ;;
  *) echo "ACTIONS must be live or simulate, got: $ACTIONS" >&2; exit 1;;
esac

require_sf_commands "agent preview start"

START_IDENTITY=()
SEND_IDENTITY=()
MODE_FLAGS=()
if [ "$TARGET" = "bundle" ]; then
  START_IDENTITY=(--authoring-bundle "$SUBJECT")
  SEND_IDENTITY=(--authoring-bundle "$SUBJECT")
  if [ "$ACTIONS" = "live" ]; then
    MODE_FLAGS=(--use-live-actions)
  else
    MODE_FLAGS=(--simulate-actions)
  fi
else
  START_IDENTITY=(-n "$SUBJECT")
  SEND_IDENTITY=(-n "$SUBJECT")
fi

end_session() {
  local sid="${SESSION_ID:-}"
  if [ -z "$sid" ]; then
    return 0
  fi
  SESSION_ID=""
  if sf agent preview end -o "$ALIAS" --session-id "$sid" --json "${SEND_IDENTITY[@]}" >"preview-end-$sid.json" 2>&1; then
    echo "Ended preview session $sid."
  else
    END_FAILED=1
    echo "WARNING: ending session $sid failed; output kept in preview-end-$sid.json." >&2
  fi
}
trap end_session EXIT INT TERM

mkdir -p "$OUT_DIR"
if [ ! -f "$TURNS" ]; then
  echo "Turns file not found: $TURNS" >&2
  exit 1
fi

if [ -n "$SEQUENCE" ]; then
  NAMES="$SEQUENCE"
else
  NAMES="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("\n".join(s["name"] for s in d["sequences"]))' "$TURNS")"
fi

for NAME in $NAMES; do
  echo "=== Sequence: $NAME ==="
  if [ "$TARGET" = "bundle" ]; then
    run_step "start preview session for $NAME" "$OUT_DIR/$NAME-start.json" \
      sf agent preview start -o "$ALIAS" --json "${START_IDENTITY[@]}" "${MODE_FLAGS[@]}"
  else
    run_step "start preview session for $NAME" "$OUT_DIR/$NAME-start.json" \
      sf agent preview start -o "$ALIAS" --json "${START_IDENTITY[@]}"
  fi
  SESSION_ID="$(verify_step preview-start "$OUT_DIR/$NAME-start.json" --expect-agent "$SUBJECT")"
  echo "Session: $SESSION_ID"
  COUNT="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len([s for s in d["sequences"] if s["name"]==sys.argv[2]][0]["turns"]))' "$TURNS" "$NAME")"
  : > "$OUT_DIR/$NAME-transcript.jsonl"
  INDEX=0
  while [ "$INDEX" -lt "$COUNT" ]; do
    UTTERANCE="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print([s for s in d["sequences"] if s["name"]==sys.argv[2]][0]["turns"][int(sys.argv[3])]["utterance"])' "$TURNS" "$NAME" "$INDEX")"
    EXPECTS="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); t=[s for s in d["sequences"] if s["name"]==sys.argv[2]][0]["turns"][int(sys.argv[3])]; print("\n".join(t.get("expect_any", [])))' "$TURNS" "$NAME" "$INDEX")"
    echo "Turn $((INDEX + 1)): $UTTERANCE"
    run_step "send turn $((INDEX + 1))" "$OUT_DIR/$NAME-turn-$INDEX.json" \
      sf agent preview send -o "$ALIAS" -u "$UTTERANCE" --session-id "$SESSION_ID" --json "${SEND_IDENTITY[@]}"
    verify_step preview-send "$OUT_DIR/$NAME-turn-$INDEX.json" --expect-session "$SESSION_ID"
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); r=d.get("result",d) if isinstance(d.get("result"),dict) else d; print(json.dumps({"utterance":sys.argv[2],"messages":r.get("messages",[])}))' \
      "$OUT_DIR/$NAME-turn-$INDEX.json" "$UTTERANCE" >> "$OUT_DIR/$NAME-transcript.jsonl"
    if [ -n "$EXPECTS" ]; then
      AGENT_TEXT="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); r=d.get("result",d) if isinstance(d.get("result"),dict) else d; print(" ".join(m.get("message","") for m in r.get("messages",[]) if isinstance(m,dict) and m.get("role")=="agent"))' "$OUT_DIR/$NAME-turn-$INDEX.json")"
      MATCHED=""
      while IFS= read -r EXPECTED; do
        [ -z "$EXPECTED" ] && continue
        case "$AGENT_TEXT" in
          *"$EXPECTED"*) MATCHED="$EXPECTED"; break;;
        esac
      done <<< "$EXPECTS"
      if [ -z "$MATCHED" ]; then
        echo "Turn $((INDEX + 1)) matched none of the expected substrings (smoke check, not semantic proof)." >&2
        TURNS_FAILED=1
      else
        echo "Turn $((INDEX + 1)) contains expected text: $MATCHED"
      fi
    fi
    INDEX=$((INDEX + 1))
  done
  end_session
done

if [ "$TURNS_FAILED" -ne 0 ]; then
  echo "One or more substring smoke checks missed. Transcripts kept under $OUT_DIR." >&2
  exit 1
fi
if [ "$END_FAILED" -ne 0 ]; then
  echo "One or more preview sessions failed to end cleanly. Transcripts kept under $OUT_DIR." >&2
  exit 1
fi
echo "Done. Transcripts kept under $OUT_DIR."
