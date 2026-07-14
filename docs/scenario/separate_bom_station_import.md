# Scenario: Import BOM and station table separately

- Given: The operator has a valid BOM and a station table for configured devices and stations
- When: The operator imports the BOM first and imports the station table in a separate action
- Then: The BOM preview appears immediately and the later station import persists a validated configuration

## Test Steps

- Case 1 (BOM only): Importing a BOM returns its product and materials without saving a configuration.
- Case 2 (station later): Importing a station table after the BOM persists exact assignments.
- Case 3 (wrong order): Reject station import when no BOM has been loaded in the current session.
- Case 4 (UI): Provide separate BOM and station import buttons with independent validation.
- Case 5 (compatibility): Keep the existing combined import workflow operational.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
