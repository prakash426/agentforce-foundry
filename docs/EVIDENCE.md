# Evidence: Service Triage complete

Handoff: Dhruv review of agentforce-foundry, Service Triage scope.
Branch: feature/service-triage-complete into foundry-features.
Pull request: https://github.com/prakash426/agentforce-foundry/pull/5
Base at start: origin/main 80d2b5681eaf9ebd658aeb2887fd5af98680c4fd (matched the reviewed commit, no newer work).
Commits on this branch:
1. 8cb52efbfe15b6cdad871ef35159b8a0fcda29fa implementation (contract, agent bundle, harness, catalog, scripts, CI, docs).
2. 83dbe5e074805315097ff0372475c37c94fc7394 first workflow fix attempt (needs bracket access).
3. 4c50ea9cc1c8475519b1d5cc3fc1b5d7120b3014 workflow gate restructure plus doc sync.

## Local checks (repo tree at 4c50ea9, run 2026-11-06 08:00:28 UTC)
1. python3 tests/harness/validate_kits.py exit 0. Six checks ok: kit readmes, service catalog with 12 scenarios valid, legacy suites present, Apex markers, permission set reference resolves to ServiceTriageAction, agent bundle with action binding.
2. python3 tests/harness/test_validate_kits.py exit 0. Thirteen tests ok: shape, positives, six negative fixture cases, two exit code cases, two audit runner cases.
3. python3 tests/eval/audit_service_scenarios.py exit 0. Seven audit checks ok. Live execution reported pending by the runner itself.
4. actionlint on both workflow files exit 0.
5. JSON parse ok for scratch def, sfdx-project, service catalog, fixtures.
6. Double hyphen scan of prose and source clean. Two long CLI flags remain in executable workflow lines only (dry run and result format), because the installed CLI offers no short form for them. Verified in local sf 2.145.6 help text.

## CI results
1. foundry-ci: success on 8cb52ef, 83dbe5e, and 4c50ea9. Offline validator, harness unit checks, scenario audit, audit artifact kept.
2. salesforce.yml on 8cb52ef: failure, run https://github.com/prakash426/agentforce-foundry/actions/runs/42183280114 with zero jobs. Cause: invalid workflow expression (dot access on hyphenated job id in needs reference).
3. salesforce.yml on 83dbe5e: failure, run https://github.com/prakash426/agentforce-foundry/actions/runs/42183832835 with zero jobs. Cause: secrets context used in job level if, which the expression rules forbid. Found via actionlint 1.7.12, fixed by moving the secret gate inside job steps.
4. salesforce.yml on 4c50ea9: all jobs success, run https://github.com/prakash426/agentforce-foundry/actions/runs/42184332585. The log at 2026-11-06T07:58:03Z shows the gate reporting no DX_AUTH_URL secret present, so org steps skipped honestly and the job passed by design. Status job confirms not run. This is a verified honest skip, not validation proof.
5. PR 5 checks on 4c50ea9: offline success, org-validate success, org-validation-status success.

## Verification layers, separated honestly
1. Offline verification: done and green, locally and in CI. Proves structure, schema validity, references, and harness behavior.
2. Apex execution: not run. No authorized org exists in this environment. Sixteen Apex tests are committed and await a first org run.
3. Deployment validation: not run. Same reason. The dry run job is ready in CI behind the secret gate.
4. Actual deployment: not run. Nothing has been installed anywhere.
5. Agent evaluation: not run. No AiEvaluationDefinition exists yet and no live conversation has happened. The static audit is not an agent run.

## Pending with exact follow ups
1. Add a DX_AUTH_URL repository secret from a validation org (sf org display with verbose json on an authorized org, store the auth URL as the secret). Rerun the salesforce workflow from the PR to get the first deploy validation plus Apex junit.
2. In an Agentforce enabled org: deploy, assign Foundry Service permission set, set the default agent user on Service_Triage_Agent, activate the agent.
3. Preview one live conversation with tests/fixtures/service-triage-inputs.json and compare against the illustrative examples in the kit README.
4. Generate a test spec with sf agent generate test-spec, create it with sf agent test create, run it with sf agent test run with wait, and keep the junit output. Compare measured outcomes against tests/testing-center/service-triage.json expectations and live_targets.
5. Convert the first measured run into updated docs: replace illustrative labels with executed evidence.

## Manual Salesforce checklist (saved for later)
1. Dev Hub access plus scratch org creation rights.
2. Deploy plus permission set assignment plus agent user (see kit README manual section).
3. Agent activation in Agentforce Studio.
4. Live preview conversation.
5. Test spec generation, creation, batch run, results kept.
6. Cleanup: delete scratch orgs when finished.

## Known limitations
1. Agent bundle syntax follows the official template pattern but has never deployed. First deploy may surface schema corrections.
2. Queue labels are suggestions, never validated against any org.
3. Motion guard and negation word lists are heuristics. Measured runs may require tuning.
4. English only. No record writes in v1 by design.
5. No Salesforce org is authorized in this environment, so all org gated proof is pending.

## Sources inspected for this work
1. https://api.github.com/repos/forcedotcom/salesforcedx-templates/contents/src/templates/project/agent/md
2. https://raw.githubusercontent.com/forcedotcom/salesforcedx-templates/main/src/templates/project/agent/ScratchDef.json
3. https://api.github.com/repos/forcedotcom/afdx-pro-code-testdrive/contents/force-app/main/default
4. https://www.salesforce.com/blog/agentforce-testing-center/?bc=OTH
5. https://trailhead.salesforce.com/content/learn/modules/agentforce-agent-testing/trust-your-agents
6. Official Local_Info_Agent.agent sample and template README (same template repo paths as items 1 and 2).
7. Installed Salesforce CLI 2.145.6 help text for agent, org, project deploy, and apex test commands.
8. actionlint 1.7.12 findings on the workflow files.

This record covers code verification through 4c50ea9. It was committed after those runs; see the pull request commits for the record commit itself.
