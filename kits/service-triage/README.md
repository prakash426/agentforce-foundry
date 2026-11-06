# Service Triage Kit

## Problem
Support requests arrive as free text. Someone must decide urgency and the right queue fast, without pretending a guess is a completed action. This kit gives a team a working starting point: an Agentforce conversation that suggests priority and queue through one tested Apex action.

## v1 contract (recommendation only)
1. The action suggests priority and queue. It creates, updates, assigns, routes, or escalates nothing.
2. Outcomes: SUGGESTED carries priority plus queue plus reason. NEEDS_CLARIFICATION means input is missing or too thin. NEEDS_REVIEW means signals conflict. Priority and queue are set only for SUGGESTED.
3. Queue labels (Critical_Response, Billing, General_Support) are suggestions. They are not validated against any org and no org queue needs to exist.
4. Input limits: subject scored on its first 255 chars, details on its first 4000. Longer inputs set truncated to true and note it in the reason.
5. Output order always matches input order. A null list returns an empty list. A null entry returns NEEDS_CLARIFICATION at its index.
6. Matching is deterministic and word based with negation handling. Substrings never match: download does not trigger down. Motion phrases such as calm down are ignored. Override style text is treated as data: beside a severity signal it forces NEEDS_REVIEW, alone it is inert because v1 takes no actions.

## Behavior map
1. triage_router welcomes and sends the request to one subagent.
2. triage_case overwrites subject and details fresh for each request, runs triage_service_case once, then follows the outcome code: present suggestions with the word suggested, ask one targeted question on NEEDS_CLARIFICATION, recommend human follow up on NEEDS_REVIEW. It transitions to escalation on explicit human requests and to off-topic handling for non support chat. Negation and uncertainty in user text are preserved into the action inputs.
3. missing_info and ambiguous_request ask for what is missing without guessing, then transition back to triage_case for scoring.
4. escalation recommends human follow up with the suggestion as context. V1 never transfers to a human; there is no Omni-Channel connection and no transfer tool.
5. off_topic redirects non support chat and reveals nothing about the system.

## Prerequisites
1. A Dev Hub enabled org plus a user who can create scratch orgs.
2. Salesforce CLI 2.x with the agent plugin available (sf agent commands resolve).
3. Python 3 for the offline harness.
4. No paid addons. v1 uses no external APIs.

## Setup (automated)
1. Run DEV_HUB=my-hub sh scripts/setup-service-triage.sh with your Dev Hub alias. It creates a scratch org, deploys Apex plus permission sets, validates the authoring bundle, publishes a candidate agent version (inactive), assigns the permission set, and runs the Service Apex tests against installed code.
2. To reuse an existing eligible dev org instead of creating a scratch org, run USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org sh scripts/setup-service-triage.sh. The org must be Agentforce enabled.
3. Org creation is the one non idempotent step: it fails if the alias exists. Delete the old org or export a new ORG_ALIAS and rerun.
4. Deploying metadata alone never creates a published executable agent version. Only sf agent publish creates the candidate version, and only sf agent activate makes a version live.

## Agent user placeholder
The committed .agent file holds an UPDATE_WITH_DEFAULT_AGENT_USER placeholder. Resolve it at publish time by exporting AGENT_USER with the agent runtime username, for example AGENT_USER=agent.user@example.com DEV_HUB=my-hub sh scripts/setup-service-triage.sh. The script swaps it for publish only and restores the placeholder so no org specific value is committed. Without AGENT_USER the script warns and publish may fail; set the default agent user in Agentforce Studio afterward instead. Never commit a real username.

## Setup (manual, pending first run)
1. Confirm the default agent user on Service_Triage_Agent in Agentforce Studio (or via AGENT_USER at publish time).
2. Assign the Foundry Service permission set to that agent user.
3. Activate a published agent version. Publishing leaves the version inactive by design.
4. Preview one conversation in live mode using the fixture inputs in tests/fixtures/service-triage-inputs.json.
5. Convert the committed scenarios with python3 tests/eval/convert_service_scenarios.py, create the test with sf agent test create, and run it with sf agent test run. Record the json results plus the candidate commit and agent version.

## Example conversations (illustrative until executed)
User: Checkout is down everywhere, registers frozen since 9am.
Agent: Suggested priority High for queue Critical_Response. Reason: severity signals found: down. This is a suggestion only. Want me to prepare a handoff note for the on call queue.

User: Where is my refund for March.
Agent: Suggested priority Medium for queue Billing. Reason: billing signals found: refund. This is a suggestion only. Anything else on this order.

User: Help.
Agent: I can triage this once I know more. What is the issue, and who or what is affected.

## Verification
1. Offline: run the python3 commands in docs/TESTING.md. All must pass with exit zero.
2. Org: rerun the Apex tests against installed code and confirm coverage, then run the agent test from converted scenarios and keep the results file with commit and version.
3. Truthfulness: confirm the agent says suggested and recommend human follow up where needed. It never says routed, assigned, saved, transferred, handed off, or escalated as a completed action in v1.

## Limitations
1. No agent run has happened yet. Conversations above are illustrative.
2. No record writes exist in v1. Human follow through is required.
3. V1 never transfers to a human. Escalation means a written recommendation, not a handoff. Real transfer would need an Omni-Channel messaging connection plus assets, which v1 does not ship.
4. Queue labels are not org validated.
5. English only in v1.

## Troubleshooting
1. Scratch create fails on alias: delete the old org or use a fresh ORG_ALIAS.
2. Validation or publish fails on the agent bundle: confirm the scratch definition includes the agent platform settings from config/project-scratch-def.json, then read the compiler error location in the json output.
3. Publish fails on the agent user: rerun with AGENT_USER set to a real username, or set the default agent user in Studio.
4. Apex tests fail: run the single class with junit output and read the first failing assertion.
5. Agent preview shows no action: confirm the permission set assignment plus agent activation, then retry.

## Cleanup
Delete the scratch org when finished so the trial allocation is released.
