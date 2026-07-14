# Step 1 - Understand Intent

## Functional Requirements

### FR-21: Build and smoke-test a Windows distribution

Provide a reproducible PyInstaller one-folder Windows build named `SMTGuard`, a project module
entry point, and a non-visible `--smoke-test` mode that composes Qt, initializes SQLite under an
explicit isolated data directory, and exits cleanly without entering the event loop or emitting
audio. Document the build and smoke commands.

## Assumptions

- The first distributable uses PyInstaller one-folder mode for reliable Qt plugin loading and
  easier diagnosis; a single-file wrapper is not required for MVP acceptance.
- The distribution root is `dist/SMTGuard/` and the executable is `SMTGuard.exe`.
- `SMT_GUARD_DATA_DIR` may override the production data directory for diagnostics and smoke tests.
- Smoke mode never shows a window and uses a silent audio adapter.
- Build outputs remain ignored by Git and may be regenerated from the spec and lock file.
