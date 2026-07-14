# Step 5 - Refactor for Maintainability

## Refactorings Completed

- FR-14: Kept workbook reading, master-data validation, and configuration persistence behind
  injected protocols and returned a frozen preview result.
- FR-15: Kept file selection and preview rendering in the UI while delegating all import rules to
  the application service.
- Added explicit OpenPyXL default-worksheet checks in integration test helpers for strict typing.

Focused verification after refactoring: 6 tests passed.
