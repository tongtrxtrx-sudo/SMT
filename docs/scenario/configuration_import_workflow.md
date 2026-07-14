# Scenario: Import and persist a validated product configuration

- Given: A BOM workbook, station workbook, enabled master data, and a product version
- When: The import service processes both workbooks
- Then: A validated configuration is persisted and a complete preview result is returned

## Test Steps

- Case 1 (happy path): Read real temporary `.xlsx` files and persist exact assignments.
- Case 2 (leading zeroes): Preserve text material codes such as `013000081` end to end.
- Case 3 (source error): Include the Excel row number when a station material is not in the BOM.
- Case 4 (worksheet error): Report a missing station worksheet and do not save a configuration.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
