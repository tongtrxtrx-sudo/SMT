# Scenario: Compose the persistent desktop application

- Given: A temporary application data directory and injected platform adapters
- When: The runtime is created, pages exchange state, and the runtime is closed or reopened
- Then: All pages share persistent repositories, refresh correctly, and release resources safely

## Test Steps

- Case 1 (navigation): Compose the eight workflow screens under stable Chinese tab labels with a
  shared current-operator control above them.
- Case 2 (persistence): Store master data, close, reopen, and read it from the same database file.
- Case 3 (page wiring): Refresh the scan configuration list after import completion.
- Case 4 (lifecycle): Allow repeated close calls and reject database use after closure.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
