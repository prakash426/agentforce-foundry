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

Branch `bug-fixes` (from `foundry-features`) into `foundry-features`,
with four focused fix branches merged in order. Fix branches share
the `bug-fixes-` prefix and parentage for grouping; git refs cannot
nest a branch under another branch name, so `bug-fixes/01-...` style
nesting was not possible. No org was touched; no version was
published, activated, or deployed from this work. Live retest is
pending user authorization after independent review.

Fix commits:
- 3027d61 admin permset idempotency
  (`bug-fixes-01-admin-permset`).
- 0e7504f dual retrieval layouts
  (`bug-fixes-02-metadata-layout`).
- cec29a8 deterministic scoring plus exact outputs
  (`bug-fixes-03-triage-execution`).
- de97952 honest limits plus override preservation
  (`bug-fixes-04-honest-responses`).

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

## Addendum: PR 7 review findings fix, offline verification

Branch `bug-fixes` into `foundry-features`.
Pull request: https://github.com/prakash426/agentforce-foundry/pull/7
Reviewed head at round start: 28f5c2b99a6a94cefeb6f03cc218c72e217205ce
(PR head, no newer work).
Fix commit: 24d10f88c6d5129b783388feb94ceb821486f97c.
Verified source commit for this record: 24d10f88c6d5129b783388feb94ceb821486f97c.
This record was committed afterward as an evidence only commit; see
the pull request commits for that commit itself. All verification
below covers the source tree at 24d10f8, not the evidence commit.
Two whitespace only uncommitted files in the working tree (the agent
bundle meta plus the Apex class meta) predate this work and are not
part of the verified commit. No org was touched; nothing was
published, activated, deployed, or queried in MIBServiceAgentOrg.

## Findings mapped to fixes and verification

1. Exact agent candidate detection. Publish diff now requires the
   expected agent identity, filters current layout tokens on exact
   identity before diffing, treats scoped legacy tokens as the
   expected agent, rejects removed versions as conflicting, and
   reports exactly one new version without blind highest version
   choice. Setup script plus scratch CI pass the identity.
   Provenance from source commit through published candidate,
   activation, resolver report, and evaluation is preserved.
   Verified by 11 new verifier cases plus 6 updated publish diff
   cases: exact two agent collision, other agent publishing alone,
   two agents adding the same number, multiple new versions, missing
   selected agent, legacy plus current plus mixed layouts, similar
   names, conflicting removed versions, malformed tokens, no blind
   highest version, missing flag, invalid identity.
2. Response contract suite in CI. The four locally passing contract
   tests now run as a required foundry-ci step after the resolver
   checks, so a failure fails the offline job. README quickstart
   plus layers table plus testing guide now list the suite
   accurately as static contract checks, never as live proof. No
   assertions changed. Verified by local run plus CI log inspection
   showing the step executing with 4 tests OK in both revised runs.
3. Independent action requirements. The catalog adds a requires_action
   flag for every scenario. Normal triage plus REVIEW outcomes
   require true; bare transfer plus directly routed clarify plus
   redirect cases stay false. The converter emits expected actions
   from the flag and records the requirement in the mapping. The
   resolver checks mapping against spec and resolves required
   actions against the selected candidate only. The checker verifies
   required actions in generated actions data and records execution
   plus assertion results separately; missing evidence cannot pass.
   Priority and queue rules unchanged. Seeded history is documented
   as context that never proves earlier execution. The trace list
   plus trace read actions path is documented for logic run proof;
   no invented spec fields are used. Verified by 9 converter cases
   (normal, uncertainty, override, bare transfer, field rules,
   invalid plus contradictory), 4 execution evidence cases (missing
   fails, action free passes, JSON evidence, similar names), 3
   resolver cases (review resolves, outside candidate fails,
   mapping mismatch fails), 4 harness negatives, and 2 mapping
   consistency cases.

## Local checks (repo tree at 24d10f8, run 2026-11-15 05:22 UTC)

1. python3 tests/harness/validate_kits.py exit 0. Eight checks ok,
   including service catalog with action requirements plus docs
   consistency over 19 real paths.
2. python3 tests/harness/test_validate_kits.py exit 0. Twenty eight
   tests ok (24 prior preserved plus 4 action requirement negatives).
3. python3 tests/eval/audit_service_scenarios.py exit 0. Ten audit
   checks ok (9 prior plus action requirements). Live execution
   reported pending by the runner itself.
4. python3 tests/eval/test_agent_eval_tools.py exit 0. Fifty four
   tests ok (39 prior preserved plus 15: 2 mapping consistency, 9
   action requirements, 4 execution evidence).
5. python3 tests/eval/test_resolve_eval_metadata.py exit 0. Nineteen
   tests ok (16 prior preserved plus 3 required action resolution).
6. python3 tests/eval/test_response_contract.py exit 0. Four tests ok,
   assertions unchanged.
7. python3 tests/shell/test_verify_sf_output.py exit 0. Fifty eight
   tests ok (47 prior preserved with 6 publish diff cases updated to
   the required identity flag, plus 11 new exact agent cases).
8. python3 tests/shell/test_script_failure_modes.py exit 0. Thirty
   five tests ok, preserved.
9. Python total: 198 tests passing (165 prior preserved, 33 added).
   Every suite exercises meaningful failures: empty and partial
   coverage, contradictory scorers, unfinished runs, mapping
   mismatches, missing execution evidence, CLI payload rejections,
   mocked command failures, and restoration checks.
10. python3 tests/eval/convert_service_scenarios.py exit 0. Twenty
    cases converted, ten requiring the action and ten action free.
11. Resolver check on the real catalog against local version 1
    metadata exit 0. Twenty cases resolved with layout
    agent-definition-version.
12. Bash syntax checks on all five org scripts plus the shared helper
    plus the fake CLI exit 0.
13. actionlint 1.7.12 on both workflow files exit 0 with no findings.
14. JSON parse ok for scratch def, sfdx-project, service catalog,
    fixtures, turns, and the legacy sample. Manifest XML parses.
15. Double hyphen scan clean in prose. Markdown table separators plus
    command flags are required syntax, not prose.
16. No org is authorized in this environment, so all org gated layers
    stay pending honestly. MIBServiceAgentOrg was never connected,
    deployed to, published in, activated in, or modified.

## CI results (all on 24d10f8, inspected via jobs plus logs)

1. foundry-ci pull request run
   https://github.com/prakash426/agentforce-foundry/actions/runs/43680648705
   success, created 2026-11-15T05:20:23Z. Offline job success with
   every step green including run response contract checks. Logs
   show the contract command executing with Ran 4 tests OK. Suite
   counts in logs match local runs exactly: 28, 54, 19, 4, 58, 35.
   Artifact service-triage-audit kept and not expired.
2. foundry-ci push run
   https://github.com/prakash426/agentforce-foundry/actions/runs/43680645491
   success, created 2026-11-15T05:20:20Z. Offline job success with
   the contract step green.
3. salesforce-validate pull request run
   https://github.com/prakash426/agentforce-foundry/actions/runs/43680648683
   success, created 2026-11-15T05:20:23Z. No DX_AUTH_URL secret
   present, so validation plus scratch steps skipped and the status
   job reported not configured honestly with This is not deployment
   proof messaging. This is a verified honest skip, not validation
   or deployment proof.

## Verification layers, separated honestly

1. Offline verification: done and green, locally and in CI. Proves
   structure, schemas, references, transitions, harness behavior,
   converter with independent action requirements, candidate scoped
   resolver, parser with execution evidence checks, thresholds,
   static reply markers, CLI payload verification with exact agent
   detection, script failure handling, and workflow lint.
2. Apex execution: not run. No authorized org exists in this
   environment. Twenty seven Apex tests are committed and await an
   org run against installed code, including the 2 new uncertainty
   tests.
3. Deployment validation: not run. Same reason. The validation only
   job is ready in CI behind the secret gate with payload
   verification.
4. Actual deployment: not run. Nothing has been installed anywhere.
5. Agent user setup: not run against a real org in this round. Prior
   live progress (deploy, permission, user creation) stands as
   observed; the rerun path with the exact agent fix awaits the
   staged retest.
6. Publishing: not run in this round. The publish step with exact
   agent version diffing is automated and mocked but has never
   executed against a real org with the new flag.
7. Activation: pending by design in the user org.
8. Agent evaluation: not run. No live conversation has happened. The
   static audit plus converter plus resolver plus checker are proven
   offline; the live run from the resolved spec with required action
   checks awaits an eligible org.
9. Sequential preview: not run. Script, modes, and turn fixtures are
   committed and mocked; no session has started. Trace reads for
   action proof await the first measured session.

## Failures and corrections

Pre-fix reproductions (expected failures, corrected by the fixes,
not verification failures): publish diff on the exact two agent
collision reported none before the fix and v2 after; the converter
emitted empty actions for REVIEW cases before the fix and the triage
action after. No post-fix verification failures occurred. Every
local suite passed on the full run after the final edit, and every
CI job succeeded on the pushed commit. No test was weakened or
removed to obtain green. Initial GitHub CLI list commands timed out
against the API; inspection proceeded through direct REST calls with
the same credentials and succeeded.

## Manual org verification: deferred

The user will retest after independent review. Nothing below blocks
this review; follow the staged procedure in docs/MANUAL_ORG_TEST.md
later in order, reusing the existing org plus runtime user.

## Known limitations and unresolved items

1. The rewritten agent bundle follows documented Agent Script
   semantics but has never compiled server side. First validate may
   surface schema corrections. It still awaits execution in the user
   org.
2. The 2 new Apex uncertainty tests still await execution in the user
   org with the other 25.
3. Queue labels are suggestions, never validated against any org.
4. Negation and uncertainty word lists are heuristics. Measured runs
   may require tuning.
5. Custom JSONPath evaluations ship empty; they need generated data
   from a first verbose run.
6. Logic run observability in the selected runner is unproven until
   the first measured run. If a required action is absent from
   invoked actions despite trace evidence, use the supported trace
   path and preserve the actions detail; no invented fields apply.
7. Legacy evaluation results expose the subject but not the tested
   version; version binding rests on recorded activation plus
   disposable org exclusivity, stated in every evaluation record.
8. Substring smoke checks in preview transcripts are signals, not
   semantic proof; wording may need tuning after the first measured
   run.
9. Agent user creation needs the Einstein Agent User profile with
   available licenses in the target org; provisioning comes from
   Agentforce enablement.
10. English only. No record writes in v1 by design. No human transfer
    in v1 by design.
11. No Salesforce org is authorized in this environment, so all org
    gated proof is pending.

## Sources inspected in round four

1. Installed @salesforce/agents spec translator: empty expectedActions
   emits no action check; non-empty asserts through the planner
   actions check with includes items against invoked actions; only
   user history turns become send steps.
2. Installed @salesforce/agents test plus results plus handler
   sources: legacy result shapes with per-expectation verdicts,
   assertion failures exit zero by design, ERROR cases set the exit.
3. Installed @salesforce/agents publisher plus connection sources:
   publish retrieval selects AiAgentDefinition types at org API 68
   and above with legacy Bot types below, publish JSON carries no
   version number, versioned full name uses Agent#VersionNumber.
4. Installed @salesforce/plugin-agent command sources for publish
   authoring-bundle, activate, test run, plus trace list and trace
   read: result shapes, version flag behavior, and the actions
   detail path for execution proof.
5. Official web search over Salesforce developer plus Testing Center
   plus Trailhead materials: snippets confirm versioned agent
   metadata, expected subagent plus expected actions plus expected
   response grading, and batch run limits. Direct page fetch was
   refused with 403, so detailed semantics rest on the installed
   sources above.

## Addendum: nested if compile failure fix, offline verification

Branch `bug-fixes` into `foundry-features`.
Pull request: https://github.com/prakash426/agentforce-foundry/pull/7
User tested commit: 745b3775ef577d452051750be2b7eb470d2cdc24
(no newer work at round start; head matched).
Fix commit: cccd030e818204f7ba579df3db4dce3252abb84c.
Verified source commit for this record: cccd030e818204f7ba579df3db4dce3252abb84c.
This record was committed afterward as an evidence only commit; see
the pull request commits for that commit itself. All verification
below covers the source tree at cccd030, not the evidence commit.
This fix work never authenticated to, queried, deployed to,
published in, activated in, or otherwise touched MY ORG. The user
ran setup in their own org; local run artifacts from that attempt
were left untracked and uncommitted.

## User observed compiler failure at 745b377

Setup on the reviewed branch, reusing the existing runtime user,
reached authoring bundle validation and stopped before publishing.
The server returned CompileAgentScriptError: AgentScript does not
support nested 'if' statements, with guidance to combine conditions
with 'and'/'or' or restructure. Location line 65, column 16,
reported range lines 65-73. Exit status 1. Cleanup restored the
local agent file afterward. The CLI update notice printed alongside
is unrelated to the cause. No candidate was published, the Apex
step was never reached, and existing activated versions were
unchanged.

## Why offline checks missed it, and what changed

Prior offline checks matched content markers in the agent file and
never parsed conditional structure, so the nested shape passed
every suite. The fix replaces the nested pair with one compound
condition using `and`, keeping the run block plus all input and
output bindings with one less indent level. Scoring behavior is
preserved: run only after a subject exists and only when the
current request has not been scored. The committed tree holds one
Agent Script file and this was its only nested conditional; a file
wide search found no other `if` statements at all. Compilation
itself stays server side: installed @salesforce/agents sources show
both validate and publish compile by posting AFScript 2.0.0 content
to a server endpoint, so no official offline parser exists. The new
regression is therefore a narrow structural scan, documented as
such, never described as server side compilation.

## Fix mapped to regression

The validator now scans the agent script for indentation nested
`if` blocks and fails the bundle check with both line numbers. The
scan accepts the corrected compound condition, accepts sibling
conditionals, flags `if` under `else`, and ignores `|` prose
lines, `#` comments, and quoted strings. It flags lines 65 plus 66
on the pre-fix file, matching the server report, and stays clean
on the fixed file plus the official Local Info Agent sample. The
check runs inside the required foundry-ci offline job through both
the validator step and the harness unit step.

## Local checks (repo tree at cccd030, run 2026-11-15 16:53 UTC)

1. python3 tests/harness/validate_kits.py exit 0. Eight checks ok.
2. python3 tests/harness/test_validate_kits.py exit 0. Thirty six
   tests ok (28 prior preserved plus 8 nested conditional cases:
   1 validator integration plus 7 focused scan cases).
3. python3 tests/eval/audit_service_scenarios.py exit 0. Ten audit
   checks ok. Live execution reported pending by the runner itself.
4. python3 tests/eval/test_agent_eval_tools.py exit 0. Fifty four
   tests ok, preserved.
5. python3 tests/eval/test_resolve_eval_metadata.py exit 0. Nineteen
   tests ok, preserved.
6. python3 tests/eval/test_response_contract.py exit 0. Four tests
   ok, preserved with the edited agent file.
7. python3 tests/shell/test_verify_sf_output.py exit 0. Fifty eight
   tests ok, preserved.
8. python3 tests/shell/test_script_failure_modes.py exit 0. Thirty
   five tests ok, preserved.
9. Python total: 206 tests passing (198 prior preserved, 8 added).
10. python3 tests/eval/convert_service_scenarios.py exit 0. Twenty
    cases converted.
11. Bash syntax checks on all five org scripts plus the shared helper
    plus the fake CLI exit 0.
12. actionlint 1.7.12 on both workflow files exit 0 with no findings.
13. Double hyphen scan clean in prose.
14. No org authorized in this environment; MY ORG untouched by this
    work.

## CI results (all on cccd030, inspected via jobs plus logs)

1. foundry-ci pull request run
   https://github.com/prakash426/agentforce-foundry/actions/runs/43738100604
   success, created 2026-11-15T16:54:36Z. Offline job success.
   Logs show the harness step with Ran 36 tests OK, proving the new
   regression executed, plus the contract command with Ran 4 tests
   OK. Suite counts match local runs exactly: 36, 54, 19, 4, 58,
   35. Artifact service-triage-audit kept and not expired.
2. foundry-ci push run
   https://github.com/prakash426/agentforce-foundry/actions/runs/43738095850
   success, created 2026-11-15T16:54:33Z. Offline job success.
3. salesforce-validate pull request run
   https://github.com/prakash426/agentforce-foundry/actions/runs/43738100555
   success, created 2026-11-15T16:54:36Z. Org gated jobs success
   through the honest no secret skip path. Not validation or
   deployment proof.

## Verification layers, separated honestly

1. Offline verification: done and green, locally and in CI. The
   corrected bundle is structurally accepted; nothing here claims it
   compiles on the server.
2. Server side validation: not run. Pending the user rerun after
   independent review, starting with the validation only checkpoint
   in docs/MANUAL_ORG_TEST.md.
3. Publishing, Apex execution, activation, evaluation, preview: all
   still pending behind validation, same as before.

## Failures and corrections

The user observed server compile failure stands as the defect
record above; the fix plus regression answer it. No post-fix
verification failures occurred. No test was weakened or removed to
obtain green.

## Known limitations and unresolved items

1. The corrected bundle has never compiled server side. First
   re-validation may surface further schema corrections.
2. The nesting scan is structural only. It tracks `if`/`else`
   indentation with prose, comment, and quote handling; it is not a
   grammar parser and cannot prove compilability.
3. All round four limitations still hold: suggested queues, heuristic
   word lists, empty custom evaluations, unproven logic run
   observability, version binding through activation records,
   smoke check wording, license needs, English only, no record
   writes, no human transfer.

## Sources inspected in round five

1. Installed @salesforce/agents script agent compile source:
   compilation posts AFScript 2.0.0 content to a server endpoint;
   no offline grammar is shipped.
2. Installed @salesforce/plugin-agent validate command source: it
   calls the same server compile path.
3. Official salesforcedx-templates Local Info Agent sample,
   fetched from the template repo: single level `if` plus `else`
   usage with no nesting, consistent with the fix shape.
4. The server error guidance itself, prescribing combined
   conditions with 'and'/'or', which the fix follows exactly.
