# Testing

## Layers
1. Offline static checks. No org needed. Prove the repo is complete and consistent. They never prove Apex or agent behavior.
2. Apex unit tests. Need an org. Prove the classifier contract. Not yet executed.
3. Agent evaluation. Needs an Agentforce enabled org with the agent activated. Proves routing and response behavior. Not yet executed.

## Commands and what each proves
1. python3 tests/harness/test_validate_kits.py proves the harness itself works: validator shape, positive repo checks, and negative fixture checks including nonzero exits.
2. python3 tests/harness/validate_kits.py proves repo consistency: kit READMEs, a valid Service scenario catalog, legacy suite presence, Apex markers, permission set references that resolve, and the agent bundle with its action binding plus transitions. Prints JSON. Exits nonzero on failure.
3. python3 tests/eval/audit_service_scenarios.py proves catalog completeness against static thresholds, multi-turn flow coverage, and fixtures. Writes tests/eval/results/service-triage-audit.json. Always reports live execution as pending. This is a static audit, not an agent run.
4. python3 tests/eval/test_agent_eval_tools.py proves the converter, result parser, and threshold enforcement work, including empty, partial, duplicate, unfinished, contradictory, and malformed fixtures. No org needed.
5. python3 tests/eval/convert_service_scenarios.py converts committed scenarios into a testing-center test spec plus mapping manifest using only platform supported fields. Exits nonzero on invalid catalogs.
6. python3 tests/eval/test_resolve_eval_metadata.py proves topic and action resolution against retrieved metadata, including missing and ambiguous fixtures. No org needed.
7. python3 tests/shell/test_verify_sf_output.py proves CLI payload verification for deploy, Apex, agent, and preview outputs. No org needed.
8. python3 tests/shell/test_script_failure_modes.py proves mocked Salesforce failures stop scripts, outputs are kept, unfinished async work fails, and the agent file is restored. No org needed.
9. python3 tests/eval/check_agent_results.py scores a live agent test run against catalog thresholds and writes a machine-readable evaluation record bound to commit, PR head, agent version, and run id. Exits nonzero on failures. Needs a live run JSON; without one there is nothing to score.
10. sf apex run test with class ServiceTriageActionTest proves the Apex contract in an org against installed code. Pending first org.
11. sf agent validate plus publish plus activate prove the bundle compiles, a candidate version exists, and a version is live. Pending first org.
12. sf agent test create plus sf agent test run from the resolved spec prove agent routing and responses in an org. Pending first org.
13. bash scripts/preview-service-triage-turns.sh proves sequential multi-turn behavior with kept transcripts. Pending first org.

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
1. foundry-ci on every push and pull request: validator, harness unit checks, scenario audit, converter and parser checks, resolver checks, verifier checks, mocked failure checks, spec conversion, shell syntax. Keeps the audit JSON plus generated specs as artifacts.
2. salesforce-validate on pull requests and manual dispatch: validation-only deploy with its own test and coverage results, kept separately from installed-code Apex runs. A disposable scratch path deploys the candidate revision first, runs Apex tests, publishes the candidate agent version, activates it inside the disposable org only, resolves spec names, creates the agent test from the resolved spec, runs it, and scores results with commit, PR head, version, and run id recorded. Every Salesforce step is verified from its JSON payload; unfinished async work fails explicitly. Fork pull requests skip org jobs entirely. Runs without a DX_AUTH_URL secret report the skip honestly. The status job distinguishes not configured, skipped, failed, validation passed, deployed, and evaluated, reading phase results from payloads rather than file presence. A skip is never presented as proof.

## Multi-turn coverage
Seeded conversation history in converted specs tests the next agent response in supplied context; it does not prove the agent produced the earlier turns. Sequential preview sessions send each utterance in order through one live session and keep the transcript, which does exercise real multi-turn behavior. Assertion failures in test runs exit zero by platform design, so scoring always goes through the checker, which fails safely on anything less than complete passing coverage.

## Pending verification
1. First validation-only deploy with captured results.
2. First disposable scratch deploy of the candidate revision.
3. First Apex test execution against installed code with coverage.
4. First candidate agent publish with recorded version.
5. First agent activation plus live preview plus sequential transcripts.
6. First Testing Center batch run from the resolved spec with measured scores.
