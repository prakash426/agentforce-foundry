# agentforce-foundry

Support teams adopting Agentforce need a triage starter they can read end to end: what the agent does, what the Apex action guarantees, how it is tested, and how to deploy it. Most samples are snippets with no tests and no measured results. Foundry answers with versioned kits plus honest verification records that separate what is proven offline from what still needs a live org.

Intended users: Salesforce developers and admins building a first support triage agent, and reviewers who want to see the contract, the tests, and the evidence before anything touches an org.

## Service Triage contract (recommendation only)

The Service Triage starter suggests a priority and a queue for each support request. It creates, updates, assigns, routes, or transfers nothing.

Outcomes from the Apex action:

- `SUGGESTED` carries priority plus queue plus reason.
- `NEEDS_CLARIFICATION` means input is missing or too thin.
- `NEEDS_REVIEW` means signals conflict, so a human should decide.

Priority and queue are set only for `SUGGESTED`. Queue labels (`Critical_Response`, `Billing`, `General_Support`) are suggestions, never validated against any org. Input limits: subject scored on its first 255 chars, details on its first 4000; longer inputs set `truncated` to true. Output order always matches input order.

## What the starter does

- Scores one support request per call through `ServiceTriageAction`, a deterministic word based classifier with clause scoped negation, contraction handling, conflict detection, and documented limits. No queries, no DML.
- Holds a multi-turn conversation through `Service_Triage_Agent`: welcomes, routes, asks one targeted clarifying question when needed, presents suggestions with the word suggested, and recommends human follow up on conflicting signals or explicit request.
- Returns to triage after clarification, moves to off-topic handling for non support chat, and never reuses stale subject or details across distinct requests.
- Treats customer text as data: override style phrases beside a severity signal force `NEEDS_REVIEW`, and alone they are inert because v1 takes no actions.

Boundaries: no record writes, no real human transfer (v1 has no messaging connection, so escalation is a written recommendation), English only, queue labels unvalidated. See [Known limitations](#known-limitations).

## Kit maturity

| Kit | Apex action plus tests | Permission set | Agent bundle | Scenario catalog | Org execution |
| --- | --- | --- | --- | --- | --- |
| Service Triage | Ready, 25 tests committed | Ready | Ready, transitions included | Ready, 17 scenarios plus 5 flows | Pending first org run |
| Sales Qualification | Ready | Ready | Pending | Legacy sample only | Pending |
| Internal Help | Ready | Ready | Pending | Legacy sample only | Pending |

Service Triage is the complete starter. Sales and Internal Help ship working Apex actions while their agent integration is still pending.

## Architecture

```text
User message
    |
triage_router (welcome plus route)
    |            |                 |               |              |
triage_case  missing_info  ambiguous_request  escalation     off_topic
    |         (ask once,      (ask once,       (recommend     (redirect,
    |          back to         back to          human          no triage
    |          triage)         triage)          follow up)     result)
    v
ServiceTriageAction (Apex, invocable)
    |
SUGGESTED (priority plus queue plus reason)
NEEDS_CLARIFICATION (one targeted question)
NEEDS_REVIEW (human follow up recommendation)
```

Details live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository structure

- [force-app](force-app): deployable source: Apex actions plus tests, permission sets, and the Service agent authoring bundle.
- [kits/service-triage](kits/service-triage): Service kit guide with contract, behavior map, setup, and troubleshooting.
- [tests/harness](tests/harness): offline static validator plus harness unit checks.
- [tests/eval](tests/eval): scenario audit, test spec converter, metadata resolver, result checker, and their tests.
- [tests/testing-center](tests/testing-center): committed scenario catalogs.
- [tests/fixtures](tests/fixtures): synthetic inputs, preview turn scripts, and a sanitized result sample.
- [tests/shell](tests/shell): CLI output verifier fixtures plus mocked script failure tests.
- [scripts](scripts): org setup, test creation, sequential preview, and output verification helpers.
- [manifests](manifests): Service validation scope manifest.
- [config](config): scratch org definition.
- [docs](docs): [architecture](docs/ARCHITECTURE.md), [testing guide](docs/TESTING.md), [evidence record](docs/EVIDENCE.md).

## Prerequisites

- Python 3.11 or newer (CI runs 3.11; scripts use the standard library only).
- Bash for org scripts (they require `pipefail` plus JSON verification).
- Salesforce CLI 2.157.8 or newer with the agent plugin. CI pins `@salesforce/cli@2.157.8`, which bundles the validate, publish, activate, and preview session commands. CLI 2.145.6 is proven to lack them; the setup script stops with update guidance on such CLIs. Agent user creation alone works on 2.145.6 and newer.
- Git plus a GitHub account for the workflows.
- For org paths: an Agentforce enabled org. Scratch orgs use Developer edition with the Einstein AI platform feature plus agent platform settings from [config/project-scratch-def.json](config/project-scratch-def.json). Source API version 60.0.

## Offline quickstart (no org)

```sh
python3 tests/harness/validate_kits.py
python3 tests/harness/test_validate_kits.py
python3 tests/eval/audit_service_scenarios.py
python3 tests/eval/test_agent_eval_tools.py
python3 tests/eval/test_resolve_eval_metadata.py
python3 tests/shell/test_verify_sf_output.py
python3 tests/shell/test_script_failure_modes.py
```

All must exit zero. These prove repo consistency, catalog validity, converter and checker behavior, output verification, and script failure handling. They never prove Apex or agent behavior; that needs an org.

## Existing Developer Edition org path

Use this when you already have an Agentforce enabled Developer Edition org. It reuses the org instead of creating a scratch org.

```sh
export ORG_ALIAS=my-dev-org
sf org login web -a my-dev-org
USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org bash scripts/setup-service-triage.sh
```

The script deploys dependencies, creates the agent runtime user (or verifies one supplied through `AGENT_USER`), assigns the custom permission set to the admin and runtime users, validates the authoring bundle, publishes an inactive candidate version, and runs Apex tests against installed code. Then follow the manual steps: activate a published version, preview, and run the converted evaluation. Full sequence below.

## Scratch org path

Needs a Dev Hub with scratch org creation rights.

```sh
DEV_HUB=my-hub bash scripts/setup-service-triage.sh
```

The script creates the agent runtime user automatically and stops before validation if user setup fails. To verify an existing user instead of creating one:

```sh
DEV_HUB=my-hub AGENT_USER=agent.user@example.com bash scripts/setup-service-triage.sh
```

Org creation fails if the alias exists; delete the old org or export a new `ORG_ALIAS` and rerun.

## Deploy, validate, publish, activate, evaluate

Each stage is distinct. The scripts and CI enforce the order and verify every step from its JSON output.

1. Deploy dependencies: Apex classes plus permission sets install first, so live actions exist before the agent runs.
2. Validation only deploy (CI): a dry run of the Service manifest with its own test and coverage results. Validation saves nothing and proves nothing about installed code.
3. Runtime user: create an agent user with the supported CLI command, or verify a supplied existing user, then assign the custom Service permission set to that user. Validation and publishing never run without a valid user.
4. Authoring bundle validation: `sf agent validate` compiles the Agent Script. A pass means it compiles, not that it is published.
5. Publish: `sf agent publish` creates an inactive candidate version plus its Bot and planner metadata, retrieved back to the project. Deployment alone never creates a version.
6. Activate: `sf agent activate` makes one version live. Publishing leaves versions inactive by design. Activation in your own org stays an explicit manual choice; CI activates only inside its disposable scratch org.
7. Apex tests: run against installed candidate code with coverage kept.
8. Agent evaluation: convert committed scenarios to a test spec, resolve names against the selected candidate version only, create the test, run it, and score results against catalog thresholds with commit, version, and run id recorded.
9. Sequential preview (optional): send scripted multi-turn conversations through preview sessions and keep transcripts.

## Agent user and permissions

The runtime user needs org platform entitlements plus the custom Apex permission set. Apex access alone is not sufficient.

- Profile: `Einstein Agent User`, provided by the CLI creation command.
- Licenses: the org must offer the agent user profile with available user licenses. Creation checks this and fails with guidance when licenses are absent or exhausted. Provisioning comes from Agentforce enablement; contact the account team for more.
- Platform permission sets, assigned by the creation command: `AgentforceServiceAgentBase`, `AgentforceServiceAgentUser`, `EinsteinGPTPromptTemplateUser`.
- Custom permission set: `Agentforce_Foundry_Service`, assigned by the setup scripts to the admin user and to the runtime user, granting Apex class access.
- The committed agent file holds an `UPDATE_WITH_DEFAULT_AGENT_USER` placeholder. Scripts resolve it to the established runtime user for validation and publishing only, then restore the placeholder automatically. Never commit a real username.
- Creation is automatic in scratch orgs (`scripts/setup-agent-user.sh` runs inside setup). In an existing org, either let the script create a user or export `AGENT_USER` with a username to verify; verification requires an active user with the required profile and platform permission sets.

## Example conversations (unexecuted)

These examples are illustrative. No live conversation has happened yet; they will be replaced with measured transcripts after the first org run.

User: Checkout is down everywhere, registers frozen since 9am.
Agent: Suggested priority High for queue Critical_Response. Reason: severity signals found: down. This is a suggestion only. For human follow up, contact your support channel directly with this suggestion as context.

User: Where is my refund for March.
Agent: Suggested priority Medium for queue Billing. Reason: billing signals found: refund. This is a suggestion only. Anything else on this order.

User: Help.
Agent: I can triage this once I know more. What is the issue, and who or what is affected.

## Automated test layers

| Layer | Command | Proves |
| --- | --- | --- |
| Static validator | `python3 tests/harness/validate_kits.py` | Files, schemas, references, transitions |
| Harness unit checks | `python3 tests/harness/test_validate_kits.py` | Validator behavior plus negative fixtures |
| Scenario audit | `python3 tests/eval/audit_service_scenarios.py` | Catalog completeness, always pending live |
| Converter plus checker | `python3 tests/eval/test_agent_eval_tools.py` | Spec conversion, scoring, thresholds |
| Metadata resolver | `python3 tests/eval/test_resolve_eval_metadata.py` | Topic and action name resolution |
| Output verifier | `python3 tests/shell/test_verify_sf_output.py` | CLI payload success markers |
| Script failure modes | `python3 tests/shell/test_script_failure_modes.py` | Fail stop behavior plus file restoration |
| Apex tests (needs org) | `sf apex run test -n ServiceTriageActionTest` | Classifier contract on installed code |
| Agent eval (needs org) | `sf agent test run` plus checker | Routing and responses per thresholds |
| Sequential preview (needs org) | `scripts/preview-service-triage-turns.sh` | Multi-turn transcripts plus smoke checks |

CI runs every offline layer on each push and pull request, plus honest org gated jobs that skip without secrets. See [docs/TESTING.md](docs/TESTING.md) for what each layer proves and never proves.

## Guides and evidence

- [Evidence record](docs/EVIDENCE.md): verified commits, commands, CI links, and pending layers.
- [Manual org test guide](docs/MANUAL_ORG_TEST.md): hands on procedure for the first live run.
- [Merge order](docs/MERGE_ORDER.md): branch flow and conflict avoidance.
- [Testing guide](docs/TESTING.md): layers, thresholds, and CI behavior.
- [Service kit guide](kits/service-triage/README.md): contract, setup, verification, and troubleshooting.
- [Architecture](docs/ARCHITECTURE.md): design, lifecycle, and security posture.

## Known limitations

- No org execution has happened yet: Apex runs, deployment, publishing, activation, preview, and agent evaluation are all pending a first authorized org.
- Agent bundle syntax follows official template patterns and locally verified command shapes but has never compiled server side.
- Queue labels are suggestions, never validated against any org.
- Negation and uncertainty word lists are heuristics; measured runs may require tuning.
- Converter topic and action names resolve against retrieved metadata; custom JSONPath evaluations ship empty until a first verbose run.
- English only. No record writes in v1. No human transfer in v1.
- Legacy evaluation results expose the subject but not the tested version; version binding rests on recorded activation plus disposable org exclusivity.

## Contributing

Feature work happens on short branches merged into `foundry-features` for joint review; `foundry-features` merges to `main` once kits verify together. Keep offline checks green (`foundry-ci`), keep org proof honest (pending until a real run), and update [docs/EVIDENCE.md](docs/EVIDENCE.md) with exact commits and results. Never commit credentials, org specific usernames, or generated result files under `tests/eval/results`.

## Official sources

Setup and platform claims rest on: installed Salesforce CLI help text for project deploy, apex test, org, and agent commands; installed `@salesforce/plugin-agent` plus `@salesforce/agents` sources for test spec, result, and scorer shapes; installed `@salesforce/plugin-apex` plus `apex-node` sources for test summary and async behavior; installed `source-deploy-retrieve` status types; the official salesforcedx-templates agent sample layout; and the Salesforce Testing Center plus Trailhead agent testing materials linked from [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

See [LICENSE](LICENSE). Independent project, not affiliated with Salesforce. Agentforce is a Salesforce trademark.
