# Scenario: Harden file boundaries and release verification

- Given: Untrusted scanned text, imported workbook archives, and arbitrary run identifiers
- When: Data is exported, workbooks are opened, records are queried, or a release is verified
- Then: Formula execution, archive exhaustion, and SQL injection are prevented and gates are repeatable

## Test Steps

- Case 1 (CSV formula): Prefix formula-triggering cells while leaving `013000081` unchanged.
- Case 2 (workbook type): Reject a non-`.xlsx` path before OpenPyXL loading.
- Case 3 (archive limits): Reject a tiny test ZIP when its injected uncompressed limit is exceeded.
- Case 4 (SQL parameters): Round-trip a SQL-like run identifier without altering the schema.
- Case 5 (verification script): Declare coverage, Ruff, Pyright, Bandit, pip-audit, build, and
  packaged smoke commands.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
