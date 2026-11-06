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
2. triage_case stores the text, runs triage_service_case once, then follows the outcome code: present suggestions with the word suggested, ask one targeted question on NEEDS_CLARIFICATION, offer the human path on NEEDS_REVIEW.
3. missing_info and ambiguous_request ask for what is missing without guessing.
4. escalation hands to a human on request.
5. off_topic redirects non support chat and reveals nothing about the system.

## Prerequisites
1. A Dev Hub enabled org plus a user who can create scratch orgs.
2. Salesforce CLI 2.x with the agent plugin available (sf agent commands resolve).
3. Python 3 for the offline harness.
4. No paid addons. v1 uses no external APIs.

## Setup (automated)
1. Run DEV_HUB=my-hub sh scripts/setup-service-triage.sh with your Dev Hub alias. It creates a scratch org, deploys the Service classes plus permission set plus agent bundle, assigns the permission set, and runs the Service Apex tests.
2. Org creation is the one non idempotent step: it fails if the alias exists. Delete the old org or export a new ORG_ALIAS and rerun.

## Setup (manual, pending first run)
1. Open Service_Triage_Agent in Agentforce Studio and set a default agent user (the committed file holds an UPDATE_WITH_DEFAULT_AGENT_USER placeholder).
2. Assign the Foundry Service permission set to that agent user.
3. Activate the agent.
4. Preview one conversation in live mode using the fixture inputs in tests/fixtures/service-triage-inputs.json.
5. Generate a test spec with sf agent generate test-spec, create it with sf agent test create, and run it with sf agent test run. Record the junit or json results.

## Example conversations (illustrative until executed)
User: Checkout is down everywhere, registers frozen since 9am.
Agent: Suggested priority High for queue Critical_Response. Reason: severity signals found: down. This is a suggestion only. Want me to prepare a handoff note for the on call queue.

User: Where is my refund for March.
Agent: Suggested priority Medium for queue Billing. Reason: billing signals found: refund. This is a suggestion only. Anything else on this order.

User: Help.
Agent: I can triage this once I know more. What is the issue, and who or what is affected.

## Verification
1. Offline: run the three python3 commands in docs/TESTING.md. All must pass with exit zero.
2. Org: rerun the Apex tests and confirm coverage, then run the agent test and keep the results file.
3. Truthfulness: confirm the agent says suggested and never routed, assigned, saved, or escalated in v1.

## Limitations
1. No agent run has happened yet. Conversations above are illustrative.
2. No record writes exist in v1. Human follow through is required.
3. Queue labels are not org validated.
4. English only in v1.

## Troubleshooting
1. Scratch create fails on alias: delete the old org or use a fresh ORG_ALIAS.
2. Deploy fails on the agent bundle: confirm the scratch definition includes the agent platform settings from config/project-scratch-def.json.
3. Apex tests fail: run the single class with junit output and read the first failing assertion.
4. Agent preview shows no action: confirm the permission set assignment plus agent activation, then retry.

## Cleanup
Delete the scratch org when finished so the trial allocation is released.
