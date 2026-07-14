# Scenario: Import BOM and station tables in a PySide6 screen

- Given: The import screen and an injected configuration import workflow
- When: An operator supplies paths, worksheet name, and version and starts import
- Then: The screen calls the workflow, previews results, or displays actionable errors

## Test Steps

- Case 1 (success): Pass normalized inputs and preview product and assignment counts.
- Case 2 (validation error): Display an import error without a modal dialog.
- Case 3 (required input): Reject blank paths or version before invoking the workflow.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
