# Scenario: Import validation

- Given: A BOM and station table are selected for import
- When: The system validates their structure and cross-references
- Then: Only a fully valid product configuration can become active

## Test Steps

- Case 1 (happy path): Accept a station material that exists in the BOM and references an enabled device and station.
- Case 2 (missing column): Reject a BOM without `商品编号` or a station table without a required column.
- Case 3 (unknown material): Reject a station material code that does not exist in the BOM.
- Case 4 (unknown device): Reject a station-table row that references an unknown or disabled device.
- Case 5 (unknown station): Reject a row whose station is not configured under the referenced device.
- Case 6 (duplicate assignment): Reject duplicate device-and-station rows within one product configuration.
- Case 7 (empty value): Reject empty device, station, or material codes and report the source row number.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
