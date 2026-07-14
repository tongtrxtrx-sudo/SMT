# Step 6 - Regression Test

## Regression Test Results

- Complete test suite executed: `uv run --offline pytest`
- Environment: `QT_QPA_PLATFORM=offscreen`
- All tests pass: Yes
- Result: 85 tests passed, 0 failed, 0 errors
- Ruff: `uv run --offline ruff check .` - passed with 0 issues
- Pyright: `uv run --offline pyright` - passed with 0 errors, 0 warnings
- Console entry point metadata: `smt-guard -> smt_guard.app:main`
- Safety: runtime databases used `TemporaryDirectory`, beep calls were injected fakes, Qt windows
  were never shown, and the production app-data path and visible entry point were not used
