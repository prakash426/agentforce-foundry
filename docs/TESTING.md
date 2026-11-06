# Testing

## Layers
1. Offline static checks. No org needed. Prove the repo is complete and consistent. They never prove Apex or agent behavior.
2. Apex unit tests. Need an org. Prove the classifier contract. Not yet executed.
3. Agent evaluation. Needs an Agentforce enabled org with the agent activated. Proves routing and response behavior. Not yet executed.

## Commands and what each proves
1. python3 tests/harness/test_validate_kits.py proves the harness itself works: validator shape, positive repo checks, and negative fixture checks including nonzero exits.
2. python3 tests/harness/validate_kits.py proves repo consistency: kit READMEs, a valid Service scenario catalog, legacy suite presence, Apex markers, permission set references that resolve, and the agent bundle with its action binding. Prints JSON. Exits nonzero on failure.
3. python3 tests/eval/audit_service_scenarios.py proves catalog completeness against static thresholds and fixtures. Writes tests/eval/results/service-triage-audit.json. Always reports live execution as pending. This is a static audit, not an agent run.
4. sf apex run test with class ServiceTriageActionTest proves the Apex contract in an org. Pending first org.
5. sf agent test create plus sf agent test run prove agent routing and responses in an org. Pending first org.

## Static thresholds
1. Every scenario category holds 2 or more scenarios.
2. Scenario ids are unique.
3. Every scenario carries notes and an expected agent behavior.
4. Every SUGGESTED scenario carries priority and queue.

## Live targets (targets, not results)
1. Normal outcome match target is 1.0.
2. Ambiguous inputs never return confident High.
3. Adversarial inputs are never obeyed.
4. Escalation inputs reach the human path.

## What CI runs
1. foundry-ci on every push and pull request: validator, harness unit checks, scenario audit. Keeps the audit JSON as an artifact.
2. salesforce-validate on pull requests and manual dispatch: deploy validation without saving, Apex run with junit, optional agent eval when configured. Runs only for same repo runs with a DX_AUTH_URL secret. Otherwise the job skips and the status job says plainly that org validation did not run. A skip is never presented as proof.

## Pending verification
1. First scratch org deploy.
2. First Apex test execution with coverage.
3. First agent preview in live mode.
4. First Testing Center batch run with measured scores.
