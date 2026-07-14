# Scenario: Append-only scan records

- Given: A production run is active
- When: Any material verification attempt is made
- Then: An immutable attempt record is appended with all traceability fields

## Test Steps

- Case 1 (OK record): Store timestamp, run, product version, device, station, expected code, scanned code, and OK result.
- Case 2 (NG record): Store an NG attempt without overwriting a previous attempt.
- Case 3 (retry): Preserve both the NG attempt and the later OK attempt for the same station.
- Case 4 (ordering): Return records in deterministic timestamp and identifier order.
- Case 5 (normal API): Do not expose update or delete operations through the application repository interface.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
