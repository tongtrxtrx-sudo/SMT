# Step 4 - Implement to Make Tests Pass

## Implementations Completed

- FR-14: Added `ConfigurationImportService` in `src/smt_guard/importing.py` to read, validate,
  persist, and summarize BOM/station imports.
- FR-15: Added `ConfigurationImportWidget` in `src/smt_guard/ui/importing.py` with workbook
  inputs, editable station sheet, version input, file selection, import action, preview table, and
  non-modal feedback.

GREEN verification executed all 6 focused tests successfully using temporary `.xlsx` files,
in-memory SQLite, and offscreen Qt widgets.
