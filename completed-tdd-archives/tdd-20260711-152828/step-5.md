# Step 5 - Refactor for Maintainability

## Refactorings Completed

- FR-22: Centralized immutable workbook defaults, kept archive checks before OpenPyXL loading,
  isolated CSV cell neutralization, and consolidated release gates in one script.
- Upgraded vulnerable pytest 8.4.2 to audited pytest 9.1.1.
- Applied Ruff-driven formatting without changing security behavior.

Security tests, real BOM import, and all release gates remained passing after refactoring.
