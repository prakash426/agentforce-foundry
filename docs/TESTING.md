# Testing
Layer 1: Apex unit tests for actions, bulk safe, must pass in scratch org.
Layer 2: Testing Center batch suites in tests/testing-center, covering routing, happy path, edge.
Layer 3: Offline validator in CI, no org needed, prints pass structure.
Run offline now with python3 tests/harness/test_validate_kits.py. Run org tests after deploy in your scratch org.
