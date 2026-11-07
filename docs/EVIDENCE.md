# Evidence: Service Triage review fixes, round two

Handoff: second review round on agentforce-foundry PR 5, Service Triage scope.
Branch: feature/service-triage-complete into foundry-features.
Pull request: https://github.com/prakash426/agentforce-foundry/pull/5
Round one fix commit: 34959d7729e400480cb627e08f80c7c7425b11a7.
Round one evidence commit: dbba1f5f400fb07a31cf4e8348ca702c88198a1f (reviewed head at round start, no newer work).
Round two fix commits: e990aee291c29d769c4e4c6b0577e297fecacc59 plus validator fix a8d9e6055d9d5f7d50350a712c74217723d4dacb.
Verified source commit for this record: a8d9e6055d9d5f7d50350a712c74217723d4dacb.
This record was committed afterward as an evidence only commit; see the pull request commits for that commit itself. All verification below covers the source tree at a8d9e60, not the evidence commit.

## What changed in round two
1. Fail safe evaluation: the checker now requires complete unique coverage of every mapped scenario, rejects missing, duplicate, unexpected, malformed, unfinished, and unknown results, rejects absent required categories, validates mapping consistency with the catalog including version match, and scores per-expectation verdicts (topic, actions, outcome) from the real legacy payload instead of any generic status. A failure record is still written on malformed input, with a failing exit.
2. Shell failure propagation: org scripts moved to bash with pipefail, run every Salesforce step through a shared helper that keeps output and propagates status, and verify each JSON payload (deploy status, Apex summary, agent validate, publish, activate, test create, test run). The agent file placeholder restores on success, failure, and interruption. Mocked failure tests prove all of this with no credentials and no org.
3. Version and run identity: CI determines the candidate version from a before and after publish diff (exactly one new version required), activates it inside the disposable scratch org only, verifies the activation echo, captures the real evaluation run id from CLI stdout, records the checkout commit plus PR head with merge commit detection, and reads every phase status from payloads rather than file presence. Legacy results expose no tested version, so the record states that binding rests on activation output plus disposable org exclusivity.
4. Automated name resolution: a resolver maps expected topics and actions against retrieved GenAi metadata by exact then unique case-insensitive match, failing before test creation on missing or ambiguous names, and ties the resolved spec to the candidate metadata snapshot. A sequential preview runner sends scripted multi-turn conversations through live sessions with transcripts. Docs state plainly that seeded history tests only the next response in context.
5. README rewrite plus reconciliation: the main README is now a full entry point (contract, maturity, architecture, structure, prerequisites, offline quickstart, existing org path, scratch path, lifecycle stages, agent user config, unexecuted examples, test layers, guides, limitations, contributing, sources, license). Kit guide, testing guide, architecture, scripts, and this record agree on commands and claims.

## Local checks (repo tree at a8d9e60, run 2026-11-07 06:15 UTC)
1. python3 tests/harness/validate_kits.py exit 0. Eight checks ok: kit readmes, service catalog with 17 scenarios valid, legacy suites present, Apex markers, permission set reference resolves, agent bundle with transitions, shell scripts use bash with verified steps, docs invoke bash and reference real paths.
2. python3 tests/harness/test_validate_kits.py exit 0. Twenty-two tests ok, including contradiction, transition, script, and docs fixtures.
3. python3 tests/eval/audit_service_scenarios.py exit 0. Nine audit checks ok. Live execution reported pending by the runner itself.
4. python3 tests/eval/test_agent_eval_tools.py exit 0. Thirty-seven tests ok: converter shape and history mapping, seven converter negatives, legacy checker pass and fail paths, empty, partial, duplicate, unexpected, unfinished, contradictory, null verdict, missing expectation, subject and run id mismatch, merge commit, failure record, six mapping consistency cases, committed sample fixture.
5. python3 tests/eval/test_resolve_eval_metadata.py exit 0. Eight tests ok: exact, case-insensitive, history, missing, ambiguous, missing action, no metadata, count mismatch.
6. python3 tests/shell/test_verify_sf_output.py exit 0. Twenty-six tests ok across deploy, Apex, agent, preview, publish diff, and envelope shapes.
7. python3 tests/shell/test_script_failure_modes.py exit 0. Nine tests ok: deploy failure stops later steps, publish failure restores the agent file, success restores and records the version, unfinished Apex fails despite zero exit, failing Apex stops activation, run failure skips scoring, in-progress run fails despite zero exit, missing version file fails before creation, full setup deploy failure stops tests.
8. python3 tests/eval/convert_service_scenarios.py exit 0. Seventeen cases converted using only verified spec fields.
9. Bash syntax checks on all four org scripts plus the shared helper plus the fake CLI exit 0.
10. actionlint 1.7.12 on both workflow files exit 0 with no findings.
11. JSON parse ok for scratch def, sfdx-project, service catalog, fixtures, turns, and the legacy sample. Manifest XML parses.
12. Double hyphen scan clean in prose. Markdown table separators in the README are required syntax, not prose. Long CLI flags remain in executable command lines only, where the installed CLI offers no short form.
13. sf org list shows no authorized orgs in this environment, so all org gated layers stay pending honestly.

## CI results
1. foundry-ci on e990aee: failure, run https://github.com/prakash426/agentforce-foundry/actions/runs/42346710390. Cause: the new docs consistency check required a generated audit path that only exists after the audit step runs; masked locally by a stale artifact. Fixed in a8d9e60 by excluding generated result paths, with a regression test.
2. foundry-ci pull request run https://github.com/prakash426/agentforce-foundry/actions/runs/42346919749 success on a8d9e60. All eight offline suites, spec conversion, shell syntax, artifacts kept.
3. salesforce pull request run https://github.com/prakash426/agentforce-foundry/actions/runs/42346919756 success on a8d9e60. No DX_AUTH_URL secret present, so validation and scratch jobs reported not configured honestly and the status job passed by design with skipped phases stated. This is a verified honest skip, not validation proof.
4. PR 5 checks on a8d9e60: offline success, org-validate success, scratch-installed-tests success, org-validation-status success.

## Verification layers, separated honestly
1. Offline verification: done and green, locally and in CI. Proves structure, schemas, references, transitions, harness behavior, converter, resolver, parser, thresholds, CLI payload verification, script failure handling, and workflow lint.
2. Apex execution: not run. No authorized org exists in this environment. Twenty-five Apex tests are committed and await a first org run against installed code.
3. Deployment validation: not run. Same reason. The validation only job is ready in CI behind the secret gate with payload verification.
4. Actual deployment: not run. Nothing has been installed anywhere.
5. Publishing: not run. The publish step with version diffing is automated but has never executed.
6. Activation: pending by design in the user org. CI activates only inside its disposable scratch org when secrets exist; that path has never executed either.
7. Agent evaluation: not run. No live conversation has happened. The static audit plus converter plus resolver plus checker are proven offline; the live run from the resolved spec awaits an eligible org.
8. Sequential preview: not run. Script and turn fixtures are committed and syntax checked; no session has started.

## Manual org verification: deferred
The user postponed org testing. Nothing below blocks this review; follow it later in order.
1. Add a DX_AUTH_URL repository secret from a Dev Hub capable org and rerun the salesforce workflow from the PR to get the first validation only results plus disposable scratch results.
2. Optionally add an AGENT_USER repository secret so the scratch path also publishes, activates in the disposable org, and evaluates; without it those phases report not configured honestly.
3. In an Agentforce enabled org: run DEV_HUB=my-hub bash scripts/setup-service-triage.sh (or USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org for an existing org), confirm the default agent user, assign the Foundry Service permission set to that user.
4. Activate a published agent version explicitly.
5. Preview one live conversation with tests/fixtures/service-triage-inputs.json, or run ORG_ALIAS=my-org bash scripts/preview-service-triage-turns.sh and compare transcripts against the illustrative examples in the README.
6. Run ORG_ALIAS=my-org AGENT_VERSION=<N> RUN_TEST=1 bash scripts/create-service-triage-test.sh, then keep the evaluation record with commit, version, and run id.
7. Convert the first measured run into updated docs: replace illustrative labels with executed evidence.
8. Cleanup: delete scratch orgs when finished.

## Known limitations and unresolved items
1. Agent bundle syntax follows official template patterns and locally verified command shapes but has never compiled server side. First validate may surface schema corrections.
2. Queue labels are suggestions, never validated against any org.
3. Negation and uncertainty word lists are heuristics. Measured runs may require tuning.
4. Custom JSONPath evaluations ship empty; they need generated data from a first verbose run.
5. Legacy evaluation results expose the subject but not the tested version; version binding rests on recorded activation plus disposable org exclusivity, stated in every evaluation record.
6. Substring smoke checks in preview transcripts are signals, not semantic proof; wording may need tuning after the first measured run.
7. English only. No record writes in v1 by design. No human transfer in v1 by design.
8. No Salesforce org is authorized in this environment, so all org gated proof is pending.

## Branch target note
PR 5 targets foundry-features, the shared integration branch, not main. That matches the repo flow: feature branches merge into foundry-features for joint review, then foundry-features merges to main once kits are verified together. These fixes travel with PR 5 into foundry-features and reach main through that later integration merge.

## Sources inspected in round two
1. Installed @salesforce/agents sources: AgentTestResultsResponse and TestCaseResult types, JSON, JUnit, and TAP conversion, NGT scorer catalog, per-expectation verdict semantics.
2. Installed @salesforce/plugin-agent sources: test run wait and timeout behavior (exit zero on assertion failures and on poll timeout), result file naming, test spec prompting fields.
3. Installed @salesforce/plugin-apex plus apex-node sources: test summary shape, per-test outcomes, async timeout returning only a run id, failure exit codes.
4. Installed source-deploy-retrieve client types: request status values plus deploy result fields.
5. Installed CLI help text for preview start, send, end, test list, org assign permset, and org create scratch, including JSON envelope support.
6. actionlint 1.7.12 findings on the workflow files (none after the validator fix).
