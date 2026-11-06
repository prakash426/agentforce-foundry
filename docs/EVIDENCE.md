# Evidence: Service Triage review fixes

Handoff: five review findings on agentforce-foundry PR 5, Service Triage scope.
Branch: feature/service-triage-complete into foundry-features.
Pull request: https://github.com/prakash426/agentforce-foundry/pull/5
Reviewed head at start: dbece89707df6de9ebecdd05fd0f0cc6e06fcd5f (no newer work, nothing overwritten).
Fix commit verified: 34959d7729e400480cb627e08f80c7c7425b11a7.
This record was committed afterward as an evidence only commit; see the pull request commits for that commit itself. All verification below covers the fix commit tree, not the evidence commit.

## What changed in the fix commit
1. Validation provenance: new manifests/service-triage-validation.xml scopes validation to Service classes plus the Service permission set. The workflow splits validation only deployment (with its own test and coverage results) from installed code tests on a disposable scratch org that deploys the candidate revision first. Results tie to candidate commit and agent version. Statuses distinguish not configured, skipped, failed, validation passed, deployed, and evaluated.
2. Transitions and multi-turn behavior: clarification subagents transition back to triage, triage transitions to escalation and off-topic handling, all transition tools are referenced in reasoning instructions, variables are overwritten fresh per request with negation and uncertainty preserved, action reruns need new information, and five executable flow scenarios were added.
3. Publishing lifecycle and honest escalation: setup script runs deploy dependencies, agent validate, agent publish (inactive candidate), Apex tests, with activation pending by design and an existing org path. The unsupported transfer tool was removed; v1 recommends human follow up and never claims a transfer. Agent user placeholder resolves at publish time only and is never committed with a real value.
4. Apex negation: straight and curly apostrophes join before matching, negation is scoped to its clause, billing respects negation, same signal affirmed plus negated is a conflict, uncertain severity goes to review. Nine new regression tests plus a ten item bulk test document each intended result.
5. Eval conversion: new converter builds a testing-center test spec plus mapping manifest from committed scenarios using only platform supported fields, with conversation history as the multi-turn path. New result checker scores live runs against catalog thresholds and writes an evaluation record bound to commit and agent version. Offline tests cover converter, parser, and thresholds including negative fixtures.

## Local checks (repo tree at 34959d7, run 2026-11-06 16:20 UTC)
1. python3 tests/harness/validate_kits.py exit 0. Six checks ok: kit readmes, service catalog with 17 scenarios valid, legacy suites present, Apex markers, permission set reference resolves to ServiceTriageAction, agent bundle with action binding and transitions.
2. python3 tests/harness/test_validate_kits.py exit 0. Eighteen tests ok, including contradiction fixtures (priority set on clarification, unknown agent behavior, turn mismatch, missing transitions, escalate tool present).
3. python3 tests/eval/audit_service_scenarios.py exit 0. Nine audit checks ok. Live execution reported pending by the runner itself.
4. python3 tests/eval/test_agent_eval_tools.py exit 0. Eighteen tests ok: converter shape and history mapping, seven converter negatives, parser pass and fail and error paths, threshold enforcement, binding and malformed input failures.
5. python3 tests/eval/convert_service_scenarios.py exit 0. Seventeen cases converted using only verified spec fields.
6. sh syntax checks on all three scripts exit 0.
7. actionlint 1.7.12 on both workflow files exit 0 with no findings.
8. JSON parse ok for scratch def, sfdx-project, service catalog, fixtures. Manifest XML parses.
9. Double hyphen scan clean in prose and docs. Long CLI flags remain in executable command lines only, where the installed CLI offers no short form (verified in sf help text for project deploy, apex test, agent validate, publish, activate, test create, and test run).
10. sf org list shows no authorized orgs in this environment, so all org gated layers stay pending honestly.

## CI results on the fix commit
1. foundry-ci pull request run https://github.com/prakash426/agentforce-foundry/actions/runs/42251952419 success on 34959d7. Validator, harness checks, scenario audit, converter and parser checks, spec conversion, shell syntax, artifacts kept.
2. salesforce pull request run https://github.com/prakash426/agentforce-foundry/actions/runs/42251952412 success on 34959d7. No DX_AUTH_URL secret present, so validation and scratch jobs reported not configured honestly and the status job passed by design with skipped phases stated. This is a verified honest skip, not validation proof.
3. PR 5 checks on 34959d7: offline success, org-validate success, scratch-installed-tests success, org-validation-status success.

## Verification layers, separated honestly
1. Offline verification: done and green, locally and in CI. Proves structure, schema validity, references, transitions, harness behavior, converter and parser behavior, and workflow lint.
2. Apex execution: not run. No authorized org exists in this environment. Twenty-five Apex tests are committed (sixteen original plus nine negation and bulk tests) and await a first org run against installed code.
3. Deployment validation: not run. Same reason. The validation only job is ready in CI behind the secret gate with its own results capture.
4. Actual deployment: not run. Nothing has been installed anywhere.
5. Publishing: not run. The publish step is automated in the setup script and CI scratch path but has never executed.
6. Activation: pending by design. Publishing leaves versions inactive; activation stays an explicit later step.
7. Agent evaluation: not run. No live conversation has happened. The static audit plus converter plus checker are proven offline; the live run from converted scenarios awaits an eligible org.

## Pending with exact follow ups
1. Add a DX_AUTH_URL repository secret from a Dev Hub capable org and rerun the salesforce workflow from the PR to get the first validation only results plus disposable scratch results.
2. Optionally add an AGENT_USER repository secret so the scratch path also publishes and evaluates; without it those phases report not configured honestly.
3. In an Agentforce enabled org: run scripts/setup-service-triage.sh with DEV_HUB (or USE_EXISTING_ORG=1 with ORG_ALIAS), confirm the default agent user, assign the Foundry Service permission set to that user.
4. Activate a published agent version explicitly.
5. Preview one live conversation with tests/fixtures/service-triage-inputs.json and compare against the illustrative examples in the kit README.
6. Run scripts/create-service-triage-test.sh with ORG_ALIAS plus AGENT_VERSION plus RUN_TEST=1, then keep the evaluation record with commit and version.
7. Convert the first measured run into updated docs: replace illustrative labels with executed evidence.

## Manual Salesforce checklist (saved for later)
1. Dev Hub access plus scratch org creation rights.
2. Deploy plus permission set assignment plus agent user (see kit README manual section).
3. Agent activation in Agentforce Studio or CLI.
4. Live preview conversation.
5. Test creation from converted spec, batch run, scored results kept.
6. Cleanup: delete scratch orgs when finished.

## Known limitations
1. Agent bundle syntax follows official template patterns and local CLI verified command shapes but has never compiled server side. First validate may surface schema corrections.
2. Queue labels are suggestions, never validated against any org.
3. Negation and uncertainty word lists are heuristics. Measured runs may require tuning.
4. Converter expectedTopic and expectedAction values use subagent and action developer names as initials; confirm against retrieved GenAi metadata after first publish.
5. Custom JSONPath evaluations ship empty; they need generated data from a first verbose run.
6. English only. No record writes in v1 by design. No human transfer in v1 by design.
7. No Salesforce org is authorized in this environment, so all org gated proof is pending.

## Claim corrections in this round
1. Escalation wording now says human follow up recommendation everywhere; removed hands to a human, transfer, and handoff completion claims from the agent, README files, architecture, and scenario notes.
2. Setup docs no longer imply metadata deployment creates an executable agent; they state only publish creates a version and only activate makes it live.
3. Workflow docs no longer present separate Apex runs as validation proof; validation results come from the validation command itself and installed code tests run only after deploying the candidate.
4. Complete in prior docs means starter scope is fully specified with offline checks, never that org execution happened. Pending layers are listed above.

## Branch target note
PR 5 targets foundry-features, the shared integration branch, not main. That matches the repo flow: feature branches merge into foundry-features for joint review, then foundry-features merges to main once kits are verified together. These fixes travel with PR 5 into foundry-features and reach main through that later integration merge.

## Sources inspected for this work
1. Installed sf CLI help text for project deploy start, apex run test, agent validate authoring-bundle, agent publish authoring-bundle, agent activate, agent preview, agent test create, agent test run, and agent generate test-spec.
2. Installed @salesforce/plugin-agent source for test spec shape (utterance, expectedTopic, expectedActions, expectedOutcome, customEvaluations, conversationHistory) and NGT scorer catalog.
3. Installed @salesforce/plugin-deploy-retrieve behavior via CLI help (dry run, manifests, coverage formatters, junit, results dir).
4. Salesforce developer guide search results for Agent Script transitions, utils reference, and agent DX publish lifecycle (direct doc pages returned access errors, so CLI help plus plugin source served as the verified reference).
5. actionlint 1.7.12 findings on the workflow files (none).
