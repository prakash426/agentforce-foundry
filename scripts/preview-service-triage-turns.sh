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
# live (real org actions) or simulate (AI mocked actions).
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

end_session() {
  if [ -n "${SESSION_ID:-}" ]; then
    sf agent preview end -o "$ALIAS" --session-id "$SESSION_ID" --json > "preview-end-$SESSION_ID.json" 2>&1 || true
    echo "Ended preview session $SESSION_ID."
    SESSION_ID=""
  fi
}
trap end_session EXIT INT TERM

agent_flags() {
  if [ "$TARGET" = "bundle" ]; then
    if [ "$ACTIONS" = "live" ]; then
      echo "--authoring-bundle $SUBJECT --use-live-actions"
    elif [ "$ACTIONS" = "simulate" ]; then
      echo "--authoring-bundle $SUBJECT --simulate-actions"
    else
      echo "ACTIONS must be live or simulate for TARGET=bundle." >&2
      exit 1
    fi
  else
    echo "-n $SUBJECT"
  fi
}

mkdir -p "$OUT_DIR"
if [ -n "$SEQUENCE" ]; then
  SEQUENCE_FILTER="$SEQUENCE"
else
  SEQUENCE_FILTER=""
fi

NAMES="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("\n".join(s["name"] for s in d["sequences"]))' "$TURNS")"
if [ -n "$SEQUENCE_FILTER" ]; then
  NAMES="$SEQUENCE_FILTER"
fi

FAILED=0
for NAME in $NAMES; do
  echo "=== Sequence: $NAME ==="
  # shellcheck disable=SC2086
  run_step "start preview session for $NAME" "$OUT_DIR/$NAME-start.json" \
    sf agent preview start -o "$ALIAS" --json $(agent_flags)
  SESSION_ID="$(verify_step preview-start "$OUT_DIR/$NAME-start.json" --expect-agent "$SUBJECT")"
  echo "Session: $SESSION_ID"
  COUNT="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len([s for s in d["sequences"] if s["name"]==sys.argv[2]][0]["turns"]))' "$TURNS" "$NAME")"
  : > "$OUT_DIR/$NAME-transcript.jsonl"
  INDEX=0
  while [ "$INDEX" -lt "$COUNT" ]; do
    UTTERANCE="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print([s for s in d["sequences"] if s["name"]==sys.argv[2]][0]["turns"][int(sys.argv[3])]["utterance"])' "$TURNS" "$NAME" "$INDEX")"
    EXPECTS="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); t=[s for s in d["sequences"] if s["name"]==sys.argv[2]][0]["turns"][int(sys.argv[3])]; print("\n".join(t.get("expect_any", [])))' "$TURNS" "$NAME" "$INDEX")"
    echo "Turn $((INDEX + 1)): $UTTERANCE"
    # shellcheck disable=SC2086
    run_step "send turn $((INDEX + 1))" "$OUT_DIR/$NAME-turn-$INDEX.json" \
      sf agent preview send -o "$ALIAS" -u "$UTTERANCE" --session-id "$SESSION_ID" --json $(agent_flags)
    verify_step preview-send "$OUT_DIR/$NAME-turn-$INDEX.json" --expect-session "$SESSION_ID"
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); r=d.get("result",d); print(json.dumps({"utterance":sys.argv[3],"messages":r.get("messages",[])}))' \
      "$OUT_DIR/$NAME-turn-$INDEX.json" "$NAME" "$UTTERANCE" >> "$OUT_DIR/$NAME-transcript.jsonl"
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
        FAILED=1
      else
        echo "Turn $((INDEX + 1)) contains expected text: $MATCHED"
      fi
    fi
    INDEX=$((INDEX + 1))
  done
  end_session
done

if [ "$FAILED" -ne 0 ]; then
  echo "One or more substring smoke checks missed. Transcripts kept under $OUT_DIR." >&2
  exit 1
fi
echo "Done. Transcripts kept under $OUT_DIR."
