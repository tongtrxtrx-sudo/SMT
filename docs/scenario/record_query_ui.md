# Scenario: Query and export verification records

- Given: Append-only attempts from multiple runs and the record screen
- When: An operator enters a run identifier, queries, or exports
- Then: Only that run is displayed and a UTF-8 CSV can be written to the chosen path

## Test Steps

- Case 1 (query): Display all columns for one run in identifier order.
- Case 2 (empty query): Show a clear no-record result.
- Case 3 (export): Export only the selected run to a temporary CSV path.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
