#!/usr/bin/env bash
# Fake Salesforce CLI for offline script failure tests. Never touches an org.
# Env: SF_LOG (invocation log), SF_FIXTURE_DIR (canned JSON outputs),
# SF_FAIL_AT (comma list of step keys that fail), SF_APEX_MODE,
# SF_RUN_MODE (alternate canned outputs for async simulation).
set -uo pipefail
# Capability probes ("--help") answer before logging: the log records
# lifecycle steps only, so ordering assertions stay meaningful.
case "$*" in
  *"--help"*)
    if [ "${SF_NO_AGENT_CMDS:-0}" = "1" ]; then
      case "$1 $2" in
        "agent validate"|"agent publish"|"agent activate"|"agent preview")
          echo "fake sf: no such command" >&2; exit 2;;
      esac
    fi
    exit 0;;
esac
echo "sf $*" >> "${SF_LOG:?}"
key=""
out=""
case "$1 $2 $3" in
  "org create scratch") key="org-create"; out="org-ok.json";;
  "org display"*) key="org-display"; out="org-ok.json";;
  "org assign permset") key="assign"; out="org-ok.json";;
  "org delete scratch") key="org-delete"; out="org-ok.json";;
  "project deploy start")
    key="deploy"
    case "$*" in
      *dry-run*) out="deploy-ok.json";;
      *) out="deploy-real-ok.json";;
    esac
    ;;
  "apex run test") key="apex"; out="${SF_APEX_MODE:-apex-ok}.json";;
  "agent validate authoring-bundle") key="validate"; out="validate-ok.json";;
  "agent publish authoring-bundle")
    key="publish"; out="publish-ok.json"
    ;;
  "agent activate") key="activate"; out="activate-ok.json";;
  "agent test create") key="create"; out="testcreate-ok.json";;
  "agent test run") key="run"; out="${SF_RUN_MODE:-testrun-ok}.json";;
  "agent preview start")
    key="preview-start"; out="preview-start-ok.json"
    case "$*" in
      *--authoring-bundle*)
        case "$*" in
          *--use-live-actions*|*--simulate-actions*) ;;
          *) echo "fake sf: bundle preview start requires exactly one action mode" >&2; exit 3;;
        esac
        ;;
    esac
    ;;
  "agent preview send")
    key="preview-send"; out="preview-send-ok.json"
    case "$*" in
      *--use-live-actions*|*--simulate-actions*)
        echo "fake sf: preview send accepts no action mode flags" >&2; exit 3;;
    esac
    case "$*" in
      *"-n "*|*--authoring-bundle*) ;;
      *) echo "fake sf: preview send requires agent identity" >&2; exit 3;;
    esac
    ;;
  "agent preview end")
    key="preview-end"; out="org-ok.json"
    case "$*" in
      *"-n "*|*--authoring-bundle*|*--all*) ;;
      *) echo "fake sf: preview end requires agent identity" >&2; exit 3;;
    esac
    ;;
  "org create agent-user") key="agent-user"; out="agentuser-ok.json";;
  "data query"*)
    key="query"
    case "$*" in
      *"FROM User"*) out="userqry-${SF_USER_MODE:-ok}.json"; key="user-query";;
      *"FROM PermissionSetAssignment"*)
        key="assign-query"
        if [ -f "${SF_LOG}.assigned" ]; then
          out="assign-full.json"
        elif [ "${SF_ASSIGN_MODE:-}" = "duplicate" ]; then
          out="assign-thin.json"
        else
          out="assign-${SF_ASSIGN_MODE:-full}.json"
        fi
        ;;
      *) echo "fake sf: no canned query for: $*" >&2; exit 2;;
    esac
    ;;
  *) echo "fake sf: no canned output for: $*" >&2; exit 2;;
esac
case ",${SF_FAIL_AT:-}," in
  *",$key,"*) echo "injected failure at $key"; exit 1;;
esac
if [ -n "${SF_STDERR_WARN:-}" ]; then
  echo "$SF_STDERR_WARN" >&2
fi
if [ "$key" = "publish" ]; then
  mkdir -p "force-app/main/default/bots/Service_Triage_Agent"
  echo "<BotVersion/>" > "force-app/main/default/bots/Service_Triage_Agent/v3.botVersion-meta.xml"
fi
if [ "$key" = "assign" ]; then
  if [ "${SF_ASSIGN_MODE:-}" = "duplicate" ]; then
    touch "${SF_LOG}.assigned"
    cat "${SF_FIXTURE_DIR:?}/permset-duplicate.json"
    exit 1
  fi
  touch "${SF_LOG}.assigned"
fi
cat "${SF_FIXTURE_DIR:?}/$out"
