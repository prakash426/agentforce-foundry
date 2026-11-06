# agentforce-foundry

Problem: support teams need a starting point for an Agentforce triage agent that is real enough to deploy and honest about what it proves. Most samples are snippets with no tests and no measured results.

Foundry v1 scope: one Service Triage starter built to a documented contract with offline checks, plus two early kits (Sales, Internal) that ship working Apex actions while their agent integration is still pending. Nothing here has run against a live org yet. What is proven and what is pending is stated in each doc.

Kit status:
1. Service Triage: complete starter pending org validation. Agent script, Apex action with tests, permission set, scenario catalog, offline checks, deploy scripts.
2. Sales Qualification: Apex action with tests plus permission set. Agent integration pending.
3. Internal Help: Apex action with tests plus permission set. Agent integration pending.

Quickstart without an org:
1. Run python3 tests/harness/test_validate_kits.py for the harness unit checks.
2. Run python3 tests/harness/validate_kits.py for the static repo audit.
3. Run python3 tests/eval/audit_service_scenarios.py for the scenario catalog audit with machine readable results.

Quickstart with an org (not yet executed by the authors):
1. Read kits/service-triage/README.md for prerequisites and the v1 contract.
2. Run DEV_HUB=my-hub sh scripts/setup-service-triage.sh to create a scratch org, deploy dependencies, validate and publish the candidate agent version, assign the permission set, and run Apex tests against installed code.
3. Complete the manual agent activation checklist in the kit README, then preview a conversation.

Verification summary: offline harness green is proven in CI. Apex execution, deployment, and agent evaluation are pending a first org run. See docs/TESTING.md for what each check proves and docs/EVIDENCE.md for the current record.

Sources used to build v1: the official salesforcedx-templates agent sample layout and scratch definition, the official afdx-pro-code-testdrive project layout, installed Salesforce CLI help text, the Salesforce Testing Center update, and the Trailhead agent testing unit. Exact links live in docs/ARCHITECTURE.md.

Independent project. Not affiliated with Salesforce. Agentforce is a Salesforce trademark.
