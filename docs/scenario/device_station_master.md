# Scenario: Device and station master data

- Given: An administrator opens system settings
- When: The administrator creates devices and configures stations manually or in bulk
- Then: Device codes are globally unique and station codes are unique within each device

## Test Steps

- Case 1 (happy path): Create `SMT-01`, then bulk-create stations `F-01` through `F-60`.
- Case 2 (duplicate device): Reject a second device with code `SMT-01`.
- Case 3 (duplicate station): Reject a second `F-01` under `SMT-01`.
- Case 4 (same station on another device): Allow `F-01` under `SMT-02`.
- Case 5 (referenced station): A station used by a product configuration can be disabled but cannot be deleted.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
