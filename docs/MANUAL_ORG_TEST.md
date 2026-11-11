# Manual org test guide: Service Triage

This is the full hands on procedure for the first live run of the Service
Triage starter. It covers what each stage proves, the exact commands, what
success looks like, what to record, and how to recover from failures.

Scope: Service Triage only. Sales Qualification and Internal Help ship Apex
actions only; their agent integration is still pending.

## What this proves

1. Deploy: Apex plus permission sets install cleanly in a real org.
2. Runtime user: an agent user exists with platform sets plus the custom
   Foundry Service set, created automatically or verified from a supplied username.
3. Bundle compile: the authoring bundle passes server side validation.
4. Publish: a candidate agent version exists and stays inactive by design.
5. Apex execution: the 25 committed classifier tests pass on installed code.
6. Activation: one version is explicitly made live.
7. Preview: scripted multi turn conversations produce transcripts.
8. Evaluation: the converted catalog runs and scores against thresholds.

What it never proves: semantic quality of agent replies. Substring smoke
checks and scorer verdicts are signals; read the transcripts before calling
behavior good.

## Prerequisites

1. This branch checked out: `feature/service-triage-complete`.
2. Salesforce CLI 2.157.8 or newer. The agent lifecycle commands
   (validate, publish, activate, preview sessions) do not exist on older
   CLIs; 2.145.6 was proven to lack them. The setup script checks this
   first and stops with update guidance when they are missing.
3. An Agentforce enabled org. Scratch orgs need a Dev Hub with creation
   rights; existing orgs must already be Agentforce enabled.
4. Available agent user licenses in the target org. Creation fails early
   with guidance when the Einstein Agent User profile has no licenses.
5. Python 3.11 or newer for the offline harness and converters.

Update the CLI before anything else:

```sh
sf update
sf --version
```

## Authenticate

Existing org path:

```sh
sf org login web -a my-dev-org
sf org display -o my-dev-org --json
```

Scratch path:

```sh
sf org login web -a my-hub
sf org display -o my-hub --json
```

Keep one alias for the whole run and reuse it in every command below.

## Run setup

Existing org:

```sh
USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org bash scripts/setup-service-triage.sh
```

Scratch org:

```sh
DEV_HUB=my-hub bash scripts/setup-service-triage.sh
```

To verify an existing runtime user instead of creating one:

```sh
USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org AGENT_USER=agent.user@example.com bash scripts/setup-service-triage.sh
```

The script runs a version gate first (Step 0), then eight steps: org
select or create, dependency deploy, admin permission set, runtime user,
bundle validation, publish, Apex tests, then activation pending notice.
Every step is verified from its JSON output, not from exit codes alone.

What success looks like:

1. Step 0 passes silently when the CLI ships the agent commands.
2. Step 4 prints the runtime username for this publish.
3. Step 6 prints the candidate agent version and writes it to
   `candidate-version-Service_Triage_Agent.txt`.
4. Step 7 keeps Apex results under `ci-results`.
5. Step 8 ends with activation pending plus the exact activate command.
6. The committed agent file is restored to its placeholder. Confirm with:

```sh
grep -n UPDATE_WITH_DEFAULT_AGENT_USER force-app/main/default/aiAuthoringBundles/Service_Triage_Agent/Service_Triage_Agent.agent
```

That grep must match. Never commit a real username.

Files produced (local only, never commit): the per step JSON captures
plus `.err` sidecars, `agent-user-<alias>.json`, the candidate version
file, and `ci-results`.

## Rerun and resume notes

1. Deploy, permission sets, validation, publish, and Apex tests are safe
   to rerun. Each publish creates a new candidate version; note which one
   you activate and evaluate.
2. Confirmed rerun issue, now fixed: setup used to stop at Step 3 on a
   rerun with `Duplicate PermissionSetAssignment` when assigning
   `Agentforce_Foundry_Service` to the admin. Step 3 now resolves the
   admin username in the targeted org, queries current assignments,
   reports already assigned and continues when present, and otherwise
   assigns plus confirms. A duplicate response on assign is accepted
   only when the payload carries that exact failure; all other
   failures still stop the script.
3. Org creation is the one non idempotent step. It fails if the alias
   exists. Delete the old org or export a new `ORG_ALIAS` and rerun.
4. Each setup run without `AGENT_USER` creates a new runtime user. On a
   rerun into the same org, reuse the earlier user to avoid duplicates:

```sh
USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org AGENT_USER=<earlier-username> bash scripts/setup-service-triage.sh
```

5. Record the trio after every setup: commit SHA, candidate version,
   runtime username mode (created or existing).

## Activate one version

Publishing leaves the version inactive. Activation is an explicit manual
choice in your own org:

```sh
sf agent activate -n Service_Triage_Agent --version N -o my-dev-org --json
```

Replace `N` with the number from the candidate version file, without a
leading `v`. Success echoes the same version back.

## Preview

Run the full scripted preview first. It sends every utterance through
live sessions and keeps transcripts under `preview-transcripts`:

```sh
ORG_ALIAS=my-dev-org bash scripts/preview-service-triage-turns.sh
```

The five sequences come from tests/fixtures/service-triage-turns.json:
help to triage, triage to human, triage to off topic, billing then
outage, and uncertain signals.

Check truthfulness in the replies: the agent says suggested for triage
results and recommends human follow up where needed. It never says
routed, assigned, saved, transferred, handed off, or escalated as a
completed action in v1.

Single sequence rerun:

```sh
ORG_ALIAS=my-dev-org SEQUENCE=help-to-triage bash scripts/preview-service-triage-turns.sh
```

Draft bundle modes, after published mode passes:

```sh
ORG_ALIAS=my-dev-org TARGET=bundle ACTIONS=live bash scripts/preview-service-triage-turns.sh
ORG_ALIAS=my-dev-org TARGET=bundle ACTIONS=simulate bash scripts/preview-service-triage-turns.sh
```

Substring misses fail the script but keep the transcripts. Those are
smoke signals, not semantic proof.

## Evaluate

Convert the catalog, resolve names against your candidate version only,
create the test, run it, and score it:

```sh
ORG_ALIAS=my-dev-org AGENT_VERSION=N RUN_TEST=1 bash scripts/create-service-triage-test.sh
```

Use the same `N` you activated. The script writes the spec and the
resolver report under `specs`, keeps run JSON under `agent-results`,
and scores through the checker. The checker verdict is the real result:
the platform exits zero on assertion failures by design.

## Recording results

Keep together for every measured run:

1. Candidate commit SHA from `git rev-parse HEAD`.
2. Agent version activated and evaluated.
3. Evaluation run id from the test run output.
4. Resolver report candidate from `specs`.
5. Apex summary from `ci-results`.
6. Preview transcripts for the five sequences.

Legacy results expose the subject but not the tested version, so version
binding rests on the recorded activation plus this trio. State that
limit in every evaluation record.

## Troubleshooting

1. Gate failure naming missing agent commands: update the CLI to 2.157.8
   or newer and rerun. Nothing ran, so nothing needs cleanup.
2. Alias exists on scratch create: delete the old org or pick a new
   `ORG_ALIAS`.
3. Agent user creation fails on profile or licenses: the org lacks
   Agentforce user provisioning. Use an enabled org or ask the account
   team about licenses.
4. Supplied `AGENT_USER` rejected: it must be active with the Einstein
   Agent User profile plus the three platform sets. Unset it to create
   a compliant user instead.
5. Validation or publish fails on the bundle: confirm the scratch
   definition in config/project-scratch-def.json carries the agent
   platform settings, then read the compiler location in the JSON.
6. Resolver rejects a name: confirm the `AGENT_VERSION` value and that
   publish retrieval exists locally. Names from another agent or version
   are rejected by design.
7. Preview shows no action: confirm the custom permission set on the
   runtime user plus activation, then retry.

## Cleanup

Delete scratch orgs when finished so the allocation is released:

```sh
sf org delete scratch -o foundry-triage
```

Leave the working tree free of run outputs before committing: per step
JSON captures, `.err` sidecars, `ci-results`, `agent-results`,
`preview-transcripts`, and `specs` are local only.
