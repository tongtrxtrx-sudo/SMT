# Scenario: Import BOM and station tables in a PySide6 screen

The active step presents a card-style workbook drop zone with a visible file-picker fallback.
Only the current BOM, station-table, or validation controls are shown.

- Given: The import screen and an injected configuration import workflow
- When: An operator follows BOM, station-table, and validation/activation steps
- Then: Each completed step reveals the next one and the final summary stays visible

## Test Steps

- Case 1 (BOM step): Pass normalized input and show product, BOM version, and material count.
- Case 2 (station step): Reveal station inputs only after the BOM succeeds and show station count.
- Case 3 (validation step): Review the combined result and enable the configuration explicitly.
- Case 4 (validation error): Display an import error without a modal dialog.
- Case 5 (required input): Reject blank paths or version before invoking the workflow.
- Case 6 (drop zone): Accept local `.xlsx`/`.xlsm` drops and show the selected filename while
  retaining the explicit file picker.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
