# Scenario: Compose the persistent desktop application

- Given: A temporary application data directory and injected platform adapters
- When: The runtime is created, pages exchange state, and the runtime is closed or reopened
- Then: All pages share persistent repositories, refresh correctly, and release resources safely

## Test Steps

- Case 1 (navigation): Compose the eight workflow screens under stable Chinese labels grouped as
  work, configuration, and system pages, with scanning first.
- Case 2 (operator): Collapse a confirmed operator to a read-only identity and switch action.
- Case 3 (persistence): Store master data, close, reopen, and read it from the same database file.
- Case 4 (page wiring): Refresh the scan configuration list after import completion.
- Case 5 (run details): Open a run's scan records directly and export them without copying its ID.
- Case 6 (empty-state navigation): Open the guided import page directly from scanning, BOM, or
  product-configuration empty states.
- Case 7 (lifecycle): Allow repeated close calls and reject database use after closure.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
