# Scenario: Query and export verification records

- Given: Append-only attempts from multiple runs and the record screen
- When: An operator enters a run identifier, queries, or exports
- Then: Only that run is displayed and a UTF-8 CSV can be written to the chosen path

## Test Steps

- Case 1 (query): Preserve all record fields in identifier order while showing only the compact
  shop-floor columns by default.
- Case 2 (summary): Show total, NG, and repeat counts above the result.
- Case 3 (empty query): Show a centered no-record state instead of a large blank table.
- Case 4 (table fit): Keep time, device, station, expected/scanned material, result, and repeat
  visible without horizontal scrolling.
- Case 5 (export): Export only the selected run to a temporary CSV path.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
