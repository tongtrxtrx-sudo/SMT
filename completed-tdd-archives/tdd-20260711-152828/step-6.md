# Step 6 - Regression Test

## Regression Test Results

- Release script: `scripts/verify_release.ps1` - exit code 0
- Complete test suite with coverage: 94 passed, 0 failed, 0 errors
- Statement coverage: 92.87%, threshold 90%
- Ruff: 0 issues
- Pyright strict: 0 errors, 0 warnings
- Bandit: 0 reported issues
- pip-audit: no known vulnerabilities; local unpublished `smt-guard` package skipped as expected
- Complexity: average cyclomatic complexity A (1.97); highest function 14, no high-risk function
- Maintainability index: all modules A
- Real supplied BOM: accepted under archive limits, product `501000087`, 24 materials, leading-zero
  material preserved
- Windows build and packaged smoke test: passed
