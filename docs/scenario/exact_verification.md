# Scenario: Exact material verification

- Given: A device and station have been selected and the station requires a known material code
- When: The operator scans a reel material code
- Then: The system returns OK only when the normalized scanned code exactly equals the required material code

## Test Steps

- Case 1 (happy path): Required `10002345` and scanned `10002345` produce OK.
- Case 2 (wrong material): Required `10002345` and scanned `10002346` produce NG.
- Case 3 (outer whitespace): Scanned ` 10002345 ` produces OK after outer whitespace is trimmed.
- Case 4 (leading zero): Required `013000081` does not match scanned `13000081`.
- Case 5 (NG recovery): After NG, scanning the correct material for the same station produces OK.
- Case 6 (repeat scan): Rechecking a completed station is recorded as a new attempt and clearly identified as a repeat.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
