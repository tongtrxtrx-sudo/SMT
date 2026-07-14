# Scenario: Result review and export

- Given: A production run contains scan attempts
- When: The operator reviews or exports the run
- Then: The system returns all attempts and writes a UTF-8 CSV with stable headers

## Test Steps

- Case 1 (review): List OK, NG, and retry attempts for the selected run.
- Case 2 (CSV export): Export all traceability fields with UTF-8 BOM for compatibility with Chinese Excel.
- Case 3 (empty run): Export headers even when the run has no attempts.
- Case 4 (special text): Correctly quote commas, quotes, and Chinese text.
- Case 5 (isolation): Do not include records from another production run.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
