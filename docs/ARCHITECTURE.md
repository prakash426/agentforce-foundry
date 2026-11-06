# Architecture

## Problem
A support team adopting Agentforce needs a triage starter they can read end to end: what the agent does, what the Apex action guarantees, how it is tested, and how to deploy it. Foundry answers with one complete Service Triage slice instead of three shallow demos.

## Design
Service Triage is recommendation only in v1. The agent collects request text, calls one invocable Apex action, and presents a suggested priority and queue with a reason. Nothing is created, updated, assigned, or routed in v1. Suggestions are labels, not completed operations.

Conversation → triage_router → triage_case → ServiceTriageAction → suggestion plus reason
Conversation → triage_router → missing_info → one clarifying question
Conversation → triage_router → ambiguous_request → one clarifying question
Conversation → triage_router → escalation → human handoff
Conversation → triage_router → off_topic → polite redirect

## Components
1. Service_Triage_Agent.agent: Agent Script blueprint modeled on the official Local Info Agent sample. Holds system rules, router, five subagents, and the action binding to apex://ServiceTriageAction with input and output mappings.
2. ServiceTriageAction.cls: deterministic classifier. Word based severity signals, negation handling, conflict detection, documented input limits, stable outcome codes. No queries, no DML.
3. Agentforce_Foundry_Service permission set: grants Apex class access for the agent runtime user.
4. Scenario catalog: twelve Service scenarios across normal, ambiguous, adversarial, out of scope, and escalation classes with expected Apex outcomes and expected agent behavior.
5. Offline harness: static validator plus scenario audit runner plus unit checks. Runs with no org.
6. Deploy path: scratch definition modeled on the official agent template, setup scripts, and CI workflows.

## Why no Flow
v1 takes no record actions and needs no branching or orchestration beyond one Apex call, so a Flow would be decorative. Escalation and clarification are conversational behaviors owned by the agent script. If a later version writes records or branches across objects, a Flow action becomes the right tool and will be added with tests.

## Security posture
Customer text is treated as data. The agent script carries explicit disregard override rules. The Apex action has no tools to abuse: override style phrases beside a severity signal force NEEDS_REVIEW, and alone they are inert. No credentials are committed. CI authentication uses a protected secret that never runs for fork pull requests.

## Kit maturity
1. Service Triage: starter complete, pending first org validation (deploy, Apex run, agent eval).
2. Sales Qualification: Apex action plus tests plus permission set. Agent script and eval pending.
3. Internal Help: Apex action plus tests plus permission set. Agent script and eval pending.

## Sources inspected for v1
1. Official agent template layout and sample: https://api.github.com/repos/forcedotcom/salesforcedx-templates/contents/src/templates/project/agent/md
2. Official agent scratch definition: https://raw.githubusercontent.com/forcedotcom/salesforcedx-templates/main/src/templates/project/agent/ScratchDef.json
3. Official DX sample project layout: https://api.github.com/repos/forcedotcom/afdx-pro-code-testdrive/contents/force-app/main/default
4. Salesforce Testing Center update (Studio move, conversation testing, custom evals): https://www.salesforce.com/blog/agentforce-testing-center/?bc=OTH
5. Trailhead agent testing unit (batch testing): https://trailhead.salesforce.com/content/learn/modules/agentforce-agent-testing/trust-your-agents
6. Installed Salesforce CLI 2.145.6 help text for agent, org, project deploy, and apex test commands (verified locally, no org needed).
