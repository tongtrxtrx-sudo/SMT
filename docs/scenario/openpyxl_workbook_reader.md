# Scenario: Read real Excel worksheets safely

- Given: An `.xlsx` workbook with a named worksheet and a header row
- When: The application reads that worksheet through the OpenPyXL adapter
- Then: It receives normalized row dictionaries with source row numbers and preserved text codes

## Test Steps

- Case 1 (happy path): Open in read-only, data-only mode and map non-empty worksheet rows.
- Case 2 (normalization): Trim surrounding whitespace while preserving leading zeroes.
- Case 3 (resource safety): Close the workbook after successful reads and mapping errors.
- Case 4 (missing sheet): Report the requested and available worksheet names.
- Case 5 (invalid header): Reject blank or duplicate headers rather than silently losing columns.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
