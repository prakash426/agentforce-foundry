# Merge order

How branches flow in this repo, what to merge next, and how to avoid
conflicts. Read this before opening or merging any pull request.

## Branch roles

1. `main` holds reviewed, jointly verified kits only. Nothing merges here
   except `foundry-features`.
2. `foundry-features` is the shared integration branch. Feature branches
   merge here for joint review first.
3. `feature/*` branches hold single kit work. They merge into
   `foundry-features`, never directly into `main`.

History uses merge commits. Do not rebase a published branch; merge the
target into the feature branch to pick up newer work instead.

## Current state

1. Open now: PR 5, `feature/service-triage-complete` into
   `foundry-features`. It is based exactly on the `foundry-features` tip,
   so no catch up merge is needed.
2. Merged already: PR 1 (scaffold), PR 2 (sales kit), PR 3 (internal
   help kit) into `foundry-features`; PR 4 (`foundry-features` into
   `main`).
3. No other feature branch is active. Local `feature/*` branches from
   merged PRs are stale and can be deleted after their remote merge is
   confirmed.

## Immediate order

1. Push `feature/service-triage-complete` with the CLI robustness fixes,
   the manual test guide, and the evidence update.
2. Wait for green checks on PR 5: offline suites, spec conversion, shell
   syntax, and the honest org gated skip.
3. Merge PR 5 into `foundry-features` with a merge commit.
4. Run the first live org pass from the manual test guide in
   docs/MANUAL_ORG_TEST.md and record measured results.
5. Open the next PR from `foundry-features` into `main` once the kits
   verify together, and merge it with a merge commit.

Never skip step 3. Merging the feature branch straight into `main` would
bypass joint review on the integration branch.

## Standing order for future kit work

1. Cut the feature branch from the tip of `foundry-features`.
2. Keep it focused on one kit. Shared files (validator, workflows,
   README tables) change only when the kit needs them.
3. Before opening the pull request, merge `foundry-features` into the
   feature branch if the target moved, and rerun the offline suite.
4. Merge feature into `foundry-features`, verify kits together, then
   merge `foundry-features` into `main`.

When two feature branches are open at once, merge the smaller one first
and have the second branch absorb the target before its own merge. This
keeps conflict resolution in one place.

## Conflict hotspots

These files are touched by almost every kit change. Expect conflicts
here and resolve them by union, not by picking one side:

1. `docs/EVIDENCE.md`: each round appends its own section. Never rewrite
   another round's section to resolve a conflict.
2. `README.md`: the kit maturity table and the guides list. Keep every
   kit row and every guide link.
3. `tests/harness/validate_kits.py`: the kit, script, and doc file
   lists. Keep entries from both sides.
4. `.github/workflows`: job and step names. Keep both jobs; shared setup
   steps merge by union.
5. `tests/testing-center` catalogs and `tests/fixtures`: additive files.
   Keep both additions.

After resolving, rerun the offline suite before pushing the resolution:

```sh
python3 tests/harness/validate_kits.py
python3 tests/eval/audit_service_scenarios.py
```

## Hygiene rules

1. Never commit credentials, org specific usernames, or generated run
   outputs: per step JSON captures, `.err` sidecars, `ci-results`,
   `agent-results`, `preview-transcripts`, `specs`, or anything under
   `tests/eval/results`.
2. Keep offline checks green on every push. A red `foundry-ci` blocks
   every merge, whatever the branch.
3. Update docs/EVIDENCE.md with exact commits and results for each
   behavior change, so the record stays reviewable.
