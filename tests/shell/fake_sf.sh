#!/usr/bin/env bash
# Fake Salesforce CLI for offline script failure tests. Never touches an org.
# Env: SF_LOG (invocation log), SF_FIXTURE_DIR (canned JSON outputs),
# SF_FAIL_AT (comma list of step keys that fail), SF_APEX_MODE,
# SF_RUN_MODE (alternate canned outputs for async simulation).
set -uo pipefail
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
  "agent preview start") key="preview-start"; out="preview-start-ok.json";;
  "agent preview send") key="preview-send"; out="preview-send-ok.json";;
  "agent preview end") key="preview-end"; out="org-ok.json";;
  *) echo "fake sf: no canned output for: $*" >&2; exit 2;;
esac
case ",${SF_FAIL_AT:-}," in
  *",$key,"*) echo "injected failure at $key"; exit 1;;
esac
if [ "$key" = "publish" ]; then
  mkdir -p "force-app/main/default/bots/Service_Triage_Agent"
  echo "<BotVersion/>" > "force-app/main/default/bots/Service_Triage_Agent/v3.botVersion-meta.xml"
fi
cat "${SF_FIXTURE_DIR:?}/$out"
