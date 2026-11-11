# Evidence: Service Triage review fixes, round three

Handoff: third review round on agentforce-foundry PR 5, Service Triage scope.
Branch: feature/service-triage-complete into foundry-features.
Pull request: https://github.com/prakash426/agentforce-foundry/pull/5
Reviewed head at round start: 155995d4f18b862c7b7fb15d6e7c0558c1a40d6c (no newer work).
Round three fix commit: 1e53a4e8654b7d546390e7ad7cfc335aad773119.
Verified source commit for this record: 1e53a4e8654b7d546390e7ad7cfc335aad773119.
This record was committed afterward as an evidence only commit; see the pull request commits for that commit itself. All verification below covers the source tree at 1e53a4e, not the evidence commit.

## Findings mapped to fixes and verification
1. Agent user setup and permission claims. New scripts/setup-agent-user.sh creates a runtime user with the supported CLI command (capturing the actual username from JSON) or verifies a supplied existing user for active status, Einstein Agent User profile, and the three platform permission sets, then assigns the custom Service permission set to that user. The setup script establishes the user before validation, always resolves the placeholder with the established name, restores the file afterward, and stops before validation when user setup fails. CI creates the user inside the disposable scratch org, so no username secret is needed or read. README, kit guide, and architecture now state the profile, license, platform, and custom requirements, replacing the Apex only claim. Verified by 8 new verifier tests plus 11 new mocked script tests covering creation, verification, missing, inactive, wrong profile, missing platform sets, failed creation, failed assignment, publish blocking, and end to end creation.
2. Sequential preview arguments. The preview script now builds separate argument arrays for start (identity plus action mode) and send (identity plus session only), validates TARGET and ACTIONS before starting, passes identity to session end, tracks turn and cleanup failures separately, and preserves transcripts in all paths. Substring checks stay labeled as smoke checks. Verified by 6 new mocked tests across published, live bundle, and simulated bundle modes, invalid modes, failed send with cleanup, and smoke miss behavior, with the fake CLI rejecting mode flags on send and identity omissions per command sources.
3. Candidate-scoped resolution. The resolver now requires agent plus version, follows the selected BotVersion through its planner to reachable topics and actions only, rejects names that exist solely in another agent or version, and fails on missing, ambiguous, malformed, or dangling references with no project-wide fallback. The report records the candidate, planner, traversed files, and per-case decisions. Setup and CI pass the verified candidate identity; the checker cross-checks the resolver report candidate against the evaluated one. The documented limit stands: legacy results do not independently expose the executed version, and operator assertion is never described as verified identity. Verified by 12 rewritten resolver tests plus 2 new checker cross-check tests.

## Local checks (repo tree at 1e53a4e, run 2026-11-07 06:55 UTC)
1. python3 tests/harness/validate_kits.py exit 0. Eight checks ok, including shell scripts (now five) and docs consistency.
2. python3 tests/harness/test_validate_kits.py exit 0. Twenty-two tests ok.
3. python3 tests/eval/audit_service_scenarios.py exit 0. Nine audit checks ok. Live execution reported pending by the runner itself.
4. python3 tests/eval/test_agent_eval_tools.py exit 0. Thirty-nine tests ok (prior thirty-seven preserved plus two resolver report cross-checks).
5. python3 tests/eval/test_resolve_eval_metadata.py exit 0. Twelve tests ok, rewritten for candidate scoping.
6. python3 tests/shell/test_verify_sf_output.py exit 0. Thirty-four tests ok (prior twenty-six preserved plus eight agent user checks).
7. python3 tests/shell/test_script_failure_modes.py exit 0. Twenty-six tests ok (prior nine preserved; eleven user setup plus six preview added).
8. Python total: 133 tests passing (102 from the prior review preserved, 31 added). Every suite exercises meaningful failures: empty and partial coverage, contradictory scorers, unfinished runs, mapping mismatches, CLI payload rejections, mocked command failures, and restoration checks.
9. python3 tests/eval/convert_service_scenarios.py exit 0. Seventeen cases converted using only verified spec fields.
10. Bash syntax checks on all five org scripts plus the shared helper plus the fake CLI exit 0.
11. actionlint 1.7.12 on both workflow files exit 0 with no findings.
12. JSON parse ok for scratch def, sfdx-project, service catalog, fixtures, turns, and the legacy sample. Manifest XML parses.
13. Double hyphen scan clean in prose. Markdown table separators in the README are required syntax, not prose.
14. sf org list shows no authorized orgs in this environment, so all org gated layers stay pending honestly.

## CI results
1. foundry-ci push run https://github.com/prakash426/agentforce-foundry/actions/runs/42349324676 success on 1e53a4e.
2. foundry-ci pull request run https://github.com/prakash426/agentforce-foundry/actions/runs/42349328230 success on 1e53a4e. All offline suites, spec conversion, shell syntax, artifacts kept.
3. salesforce pull request run https://github.com/prakash426/agentforce-foundry/actions/runs/42349328351 success on 1e53a4e. No DX_AUTH_URL secret present, so validation and scratch jobs reported not configured honestly. This is a verified honest skip, not validation or deployment proof.

## Verification layers, separated honestly
1. Offline verification: done and green, locally and in CI. Proves structure, schemas, references, transitions, harness behavior, converter, candidate-scoped resolver, parser, thresholds, CLI payload verification, script failure handling, and workflow lint.
2. Apex execution: not run. No authorized org exists in this environment. Twenty-five Apex tests are committed and await a first org run against installed code.
3. Deployment validation: not run. Same reason. The validation only job is ready in CI behind the secret gate with payload verification.
4. Actual deployment: not run. Nothing has been installed anywhere.
5. Agent user setup: not run against a real org. Creation and verification paths are automated and mocked; the first real user creation awaits an eligible org.
6. Publishing: not run. The publish step with version diffing is automated but has never executed.
7. Activation: pending by design in the user org.
8. Agent evaluation: not run. No live conversation has happened. The static audit plus converter plus resolver plus checker are proven offline; the live run from the resolved spec awaits an eligible org.
9. Sequential preview: not run. Script, modes, and turn fixtures are committed and mocked; no session has started.

## Manual org verification: deferred
The user postponed org testing. Nothing below blocks this review; follow it later in order.
1. Add a DX_AUTH_URL repository secret from a Dev Hub capable org and rerun the salesforce workflow from the PR to get the first validation only results plus disposable scratch results (user creation, publish, disposable activation, evaluation).
2. In an Agentforce enabled org: run DEV_HUB=my-hub bash scripts/setup-service-triage.sh (or USE_EXISTING_ORG=1 ORG_ALIAS=my-dev-org for an existing org). The script creates the runtime user automatically, or export AGENT_USER to verify an existing one.
3. Activate a published agent version explicitly.
4. Preview one live conversation with tests/fixtures/service-triage-inputs.json, or run ORG_ALIAS=my-org bash scripts/preview-service-triage-turns.sh (published, live bundle, or simulated bundle) and compare transcripts against the illustrative examples in the README.
5. Run ORG_ALIAS=my-org AGENT_VERSION=<N> RUN_TEST=1 bash scripts/create-service-triage-test.sh, then keep the evaluation record with commit, version, and run id.
6. Convert the first measured run into updated docs: replace illustrative labels with executed evidence.
7. Cleanup: delete scratch orgs when finished.

## Known limitations and unresolved items
1. Agent bundle syntax follows official template patterns and locally verified command shapes but has never compiled server side. First validate may surface schema corrections.
2. Queue labels are suggestions, never validated against any org.
3. Negation and uncertainty word lists are heuristics. Measured runs may require tuning.
4. Custom JSONPath evaluations ship empty; they need generated data from a first verbose run.
5. Legacy evaluation results expose the subject but not the tested version; version binding rests on recorded activation plus disposable org exclusivity, stated in every evaluation record.
6. Substring smoke checks in preview transcripts are signals, not semantic proof; wording may need tuning after the first measured run.
7. Agent user creation needs the Einstein Agent User profile with available licenses in the target org; provisioning comes from Agentforce enablement.
8. English only. No record writes in v1 by design. No human transfer in v1 by design.
9. No Salesforce org is authorized in this environment, so all org gated proof is pending.

## Branch target note
PR 5 targets foundry-features, the shared integration branch, not main. That matches the repo flow: feature branches merge into foundry-features for joint review, then foundry-features merges to main once kits are verified together. These fixes travel with PR 5 into foundry-features and reach main through that later integration merge.

## Sources inspected in round three
1. CLI reference plus installed help for org create agent-user on 2.145.6 and on the pinned CI 2.157.8 (flags, profile, permission sets, license checks).
2. Installed @salesforce/plugin-org agent-user command source: result fields, license and profile verification, permission set assignment.
3. Official plugin-agent command sources for preview start, send, and end: accepted flags, required identity, result shapes.
4. Installed @salesforce/agents sources for BotVersion, planner bundle, plugin, and function reference structures used by candidate scoping.
5. actionlint 1.7.12 findings on the workflow files (none).

## Addendum: first live run notes, 2026-11-08 (after round three)

First setup attempt ran against an existing Agentforce enabled Developer
Edition org. No usernames or org identifiers are recorded here; run
captures stayed local and uncommitted.

1. Stream pollution bug, found at setup step 1. The CLI printed an update
   notice into the merged capture file and the verifier rejected the
   payload. Fixed by splitting stdout from stderr in the step helper
   (stderr now goes to a `.err` sidecar) plus preamble tolerance in the
   verifier, which still rejects trailing garbage and pure garbage.
   Covered by 4 verifier tests and 2 mocked script tests.
2. Live progress on the rerun: dependency deploy Succeeded, admin
   permission set assigned, agent runtime user created with the custom
   permission set, and the agent file restored to its placeholder after
   the stop. Deploy, permission, and user creation paths are now proven
   against a real org.
3. CLI floor discovery at the validate step. CLI 2.145.6 (plugin-agent
   1.44.5) has no validate, publish, activate, or preview session
   commands, so validation stopped with a "not a sf command" error.
   Verified via npm inspection that the pinned CLI 2.157.8 (plugin-agent
   2.2.3) ships all six lifecycle commands, and that every flag shape in
   the scripts matches the plugin sources for 2.2.3 and 2.2.4. Added a
   capability gate that probes the required commands before any org
   mutation and stops with update guidance, covered by 2 mocked script
   tests. Minimum CLI is now 2.157.8 in the README and kit guide.
4. Python total is now 141 tests passing (133 from round three plus 8
   added here). Full offline suite green after the final edit.
5. Still pending: rerun setup on CLI 2.157.8 or newer following
   docs/MANUAL_ORG_TEST.md, then activate, preview, and evaluate. The
   rerun should reuse the created runtime user through `AGENT_USER` to
   avoid duplicates.

## Addendum: acceptance-failure fixes, offline verification

Branch `foundry-features/bug-fixes` into `foundry-features`, with four
focused fix branches merged in order. No org was touched; no version
was published, activated, or deployed from this work. Live retest is
pending user authorization after independent review.

Fix commits:
- 3027d61 admin permset idempotency
  (`foundry-features/bug-fixes-01-admin-permset`).
- 0e7504f dual retrieval layouts
  (`foundry-features/bug-fixes-02-metadata-layout`).
- cec29a8 deterministic scoring plus exact outputs
  (`foundry-features/bug-fixes-03-triage-execution`).
- de97952 honest limits plus override preservation
  (`foundry-features/bug-fixes-04-honest-responses`).

Offline verification on the merged integration tree plus docs
(run 2026-11-11 19:22 UTC, all exit zero):
- validate_kits.py ok, including deterministic scoring markers.
- test_validate_kits.py: 24 tests ok.
- audit_service_scenarios.py ok on 20 scenarios.
- test_agent_eval_tools.py: 39 tests ok.
- test_resolve_eval_metadata.py: 16 tests ok (both layouts).
- test_response_contract.py: 4 tests ok.
- test_verify_sf_output.py: 47 tests ok.
- test_script_failure_modes.py: 35 tests ok.
- Python total: 165 tests passing.
- Bash syntax checks on all org scripts plus helpers plus fake CLI.
- Catalog converts to 20 cases; resolver reports layout per candidate.
- No double hyphens in prose (verified by scan).

Apex: 27 tests committed (25 prior plus 2 uncertainty). Source checks
ran offline only; org execution of the 2 new tests is pending. No
Python copy of Apex logic was substituted for execution.

Live retest pending: staged existing-org procedure in
docs/MANUAL_ORG_TEST.md with checkpoints for setup rerun, action
invocation traces, exact reply values, honest limits, uncertainty,
and override handling. Transcripts and trace evidence must be
preserved with the run record. See docs/BUG_MATRIX.md for the
bug-to-regression map. Old Version 1 conversation behavior is failed
acceptance testing; nothing here claims org verification of fixes.

Remaining limitations: deterministic Agent Script logic follows
documented semantics but has not compiled server side; the rewritten
bundle shape awaits first validate. Publish JSON carries no version,
so candidate identity still rests on retrieval diff plus resolver
report plus recorded activation. Custom JSONPath evaluations ship
empty. Legacy results expose subject but not version.
