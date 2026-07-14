# Step 6 - Regression Test

## Regression Test Results

- Lock verification: `uv lock --check` - passed
- Complete test suite: `uv run --offline pytest` - 89 passed, 0 failed, 0 errors
- Ruff: `uv run --offline ruff check .` - passed with 0 issues
- Pyright: `uv run --offline pyright` - passed with 0 errors, 0 warnings
- Windows build: `scripts/build_windows.ps1` - completed successfully
- Distribution: `dist/SMTGuard/SMTGuard.exe`, 172 files, 117,764,832 total bytes
- Packaged smoke test: exit code 0, temporary SQLite created, no visible window, temporary directory
  removed after verification
- Safety: smoke data used a verified system temporary path; production app data and audio were not
  touched
