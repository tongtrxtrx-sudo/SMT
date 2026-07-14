# Scenario: Provide a station-table Excel template

- Given: An operator needs to prepare station assignments outside the application
- When: The operator opens the supplied Excel template
- Then: The workbook clearly documents and preserves the exact import format

## Test Steps

- Case 1 (structure): Provide `Worksheet` with the three required headers in import order.
- Case 2 (code safety): Store the example material code as text so its leading zero is preserved.
- Case 3 (usability): Include Chinese instructions, styled headers, frozen header row, filter, widths, and print settings.
- Case 4 (distribution): Copy the template beside `SMTGuard.exe` during the Windows build.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
