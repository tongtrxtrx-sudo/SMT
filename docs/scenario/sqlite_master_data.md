# Scenario: Persist device and station master data

- Given: An initialized in-memory SQLite database
- When: Devices and stations are created, disabled, referenced, or deleted
- Then: Existing master-data rules are enforced and state is visible through a new repository

## Test Steps

- Case 1 (persistence): Create device/station data and reload it through another repository.
- Case 2 (uniqueness): Reject duplicate device and device-local station codes.
- Case 3 (bulk): Create a formatted station range atomically.
- Case 4 (lifecycle): Persist disabled state and protect referenced stations from deletion.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
