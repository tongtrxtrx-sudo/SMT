# Step 1 - Understand Intent

## Functional Requirements

### FR-9: Read real Excel worksheets safely

Provide an OpenPyXL-backed workbook reader for BOM and station-table `.xlsx` files. The reader
must open workbooks in read-only, data-only mode, select the requested worksheet, map the first
row to column names, retain the original Excel row number, trim only surrounding whitespace from
text values, preserve leading zeroes in text codes, and close the workbook after either success or
failure. Missing sheets and ambiguous headers must produce a clear import error.

## Assumptions

- The first worksheet row is the header row.
- Completely empty data rows are ignored.
- Blank or duplicate column names are rejected because they cannot be mapped safely to a row
  dictionary.
- Leading zeroes can be preserved when the source cell is stored as Excel text. Numeric Excel
  cells cannot reconstruct zeroes that Excel has already discarded.
- OpenPyXL is imported lazily so isolated tests can use an injected workbook loader before project
  dependencies are installed.
