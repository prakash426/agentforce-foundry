# Architecture

## Problem
A support team adopting Agentforce needs a triage starter they can read end to end: what the agent does, what the Apex action guarantees, how it is tested, and how to deploy it. Foundry answers with one complete Service Triage slice instead of three shallow demos.

## Design
Service Triage is recommendation only in v1. The agent collects request text, calls one invocable Apex action, and presents a suggested priority and queue with a reason. Nothing is created, updated, assigned, or routed in v1. Suggestions are labels, not completed operations.

Conversation → triage_router → triage_case → ServiceTriageAction → suggestion plus reason
Conversation → triage_router → missing_info → one clarifying question → back to triage_case
Conversation → triage_router → ambiguous_request → one clarifying question → back to triage_case
Conversation → triage_case → escalation → human follow up recommendation (no transfer in v1)
Conversation → triage_case → off_topic → polite redirect
Conversation → triage_router → escalation or off_topic directly for explicit human requests and non support chat

## Components
1. Service_Triage_Agent.agent: Agent Script blueprint modeled on the official Local Info Agent sample. Holds system rules, router, five subagents with transitions, and the action binding to apex://ServiceTriageAction with input and output mappings.
2. ServiceTriageAction.cls: deterministic classifier. Word based severity signals, clause scoped negation with contraction handling, conflict and uncertainty detection, documented input limits, stable outcome codes. No queries, no DML.
3. Agentforce_Foundry_Service permission set: grants Apex class access for the agent runtime user.
4. Scenario catalog: seventeen Service scenarios across normal, ambiguous, adversarial, out of scope, and escalation classes with expected Apex outcomes, expected agent behavior, and five multi-turn flows.
5. Offline harness: static validator plus scenario audit runner plus unit checks. Runs with no org.
6. Eval toolchain: scenario converter, candidate-scoped metadata resolver, result checker with thresholds, CLI output verifier, and mocked script failure tests. All run with no org. The resolver follows the selected candidate version through its planner (legacy BotVersion chain or inline agent definition version) to reachable topics and actions only; the checker cross-checks the resolver report candidate against the evaluated one.
7. Deploy path: scratch definition modeled on the official agent template, verified setup scripts, sequential preview runner, and CI workflows.

## Why no Flow
v1 takes no record actions and needs no branching or orchestration beyond one Apex call, so a Flow would be decorative. Human follow up recommendations and clarification are conversational behaviors owned by the agent script. If a later version writes records or branches across objects, a Flow action becomes the right tool and will be added with tests.

## Agent lifecycle
Deploying metadata alone never creates a published executable agent version. The supported sequence is: deploy Apex plus permission sets, establish the agent runtime user, run sf agent validate authoring-bundle as a compile check, run sf agent publish authoring-bundle to create an inactive candidate version (agent metadata retrieved back to the project in either the legacy bots layout or the current aiAgentDefinitionVersions layout), then run sf agent activate for one version when ready. Tests and preview run against the activated published agent, never against the draft bundle, except bundle preview modes that target the draft explicitly. The committed .agent file keeps an agent user placeholder that is resolved to the established user for validation and publishing only, then restored, never committed with a real value.

Supported metadata and API boundary: source API version is 60.0 (pinned in sfdx-project.json). Live org responses have been observed at API 68.0. Both retrieval layouts are supported and the tooling accepts either; no behavior branches on API version, and no layout difference is attributed to an API version without evidence. Publish JSON carries no version number, so the candidate version is identified from the retrieval diff (exactly one new version across both layouts), then verified through the resolver report and recorded activation. File existence alone never proves publish success.

## Agent runtime user
Publishing requires a valid runtime user first. The setup creates one with the supported org command, which provisions the Einstein Agent User profile plus the AgentforceServiceAgentBase, AgentforceServiceAgentUser, and EinsteinGPTPromptTemplateUser permission sets after checking license availability. The setup then assigns the custom Agentforce_Foundry_Service permission set to the runtime user for Apex access. An explicitly supplied existing user must already be active with the same profile and platform permission sets, or verification fails with guidance. Apex class access alone never satisfies the runtime requirements.

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
6. Installed Salesforce CLI help text for agent, org, project deploy, and apex test commands (verified locally, no org needed).
7. Installed plugin sources: agent plugin plus agents library for test spec, result, and scorer shapes; apex plugin plus apex-node for test summary and async behavior; source-deploy-retrieve for deploy status types.
