# Testing

## Layers
1. Offline static checks. No org needed. Prove the repo is complete and consistent. They never prove Apex or agent behavior.
2. Apex unit tests. Need an org. Prove the classifier contract. Not yet executed.
3. Agent evaluation. Needs an Agentforce enabled org with the agent activated. Proves routing and response behavior. Not yet executed.

## Commands and what each proves
1. python3 tests/harness/test_validate_kits.py proves the harness itself works: validator shape, positive repo checks, and negative fixture checks including nonzero exits.
2. python3 tests/harness/validate_kits.py proves repo consistency: kit READMEs, a valid Service scenario catalog, legacy suite presence, Apex markers, permission set references that resolve, and the agent bundle with its action binding plus transitions. Prints JSON. Exits nonzero on failure.
3. python3 tests/eval/audit_service_scenarios.py proves catalog completeness against static thresholds, multi-turn flow coverage, and fixtures. Writes tests/eval/results/service-triage-audit.json. Always reports live execution as pending. This is a static audit, not an agent run.
4. python3 tests/eval/test_agent_eval_tools.py proves the converter, result parser, and threshold enforcement work, including negative fixtures. No org needed.
5. python3 tests/eval/convert_service_scenarios.py converts committed scenarios into a testing-center test spec plus mapping manifest using only platform supported fields. Exits nonzero on invalid catalogs.
6. python3 tests/eval/check_agent_results.py scores a live agent test run against catalog thresholds and writes a machine-readable evaluation record bound to commit and agent version. Exits nonzero on failures. Needs a live run JSON; without one there is nothing to score.
7. sf apex run test with class ServiceTriageActionTest proves the Apex contract in an org against installed code. Pending first org.
8. sf agent validate plus publish plus activate prove the bundle compiles, a candidate version exists, and a version is live. Pending first org.
9. sf agent test create plus sf agent test run from the converted spec prove agent routing and responses in an org. Pending first org.

## Static thresholds
1. Every scenario category holds 2 or more scenarios.
2. Scenario ids are unique.
3. Every scenario carries notes and an expected agent behavior.
4. Every SUGGESTED scenario carries priority and queue. CLARIFICATION and REVIEW scenarios carry neither.
5. Agent behavior values come from a fixed set: run_triage, clarify, redirect, escalate.
6. Five or more multi-turn flow scenarios exist for conversion, each ending in its stated input.

## Live targets (targets, not results)
1. Normal outcome match target is 1.0.
2. Ambiguous inputs never return confident High.
3. Adversarial inputs are never obeyed.
4. Escalation inputs reach the human follow up recommendation path. V1 never transfers.

## What CI runs
1. foundry-ci on every push and pull request: validator, harness unit checks, scenario audit, converter and parser checks. Keeps the audit JSON plus generated specs as artifacts.
2. salesforce-validate on pull requests and manual dispatch: validation-only deploy with its own test and coverage results, kept separately from installed-code Apex runs. A disposable scratch path deploys the candidate revision first, then runs Apex tests, publishes the candidate agent version, and runs the converted agent test when configured. Fork pull requests skip org jobs entirely. Runs without a DX_AUTH_URL secret report the skip honestly. The status job distinguishes not configured, skipped, failed, validation passed, deployed, and evaluated. A skip is never presented as proof.

## Pending verification
1. First validation-only deploy with captured results.
2. First disposable scratch deploy of the candidate revision.
3. First Apex test execution against installed code with coverage.
4. First candidate agent publish with recorded version.
5. First agent activation plus live preview.
6. First Testing Center batch run from converted scenarios with measured scores.
