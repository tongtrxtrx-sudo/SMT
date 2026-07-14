# Scenario: Build and smoke-test a Windows distribution

- Given: The locked project environment and Windows packaging configuration
- When: The build script creates the distribution and the executable runs in smoke mode
- Then: Qt and SQLite compose successfully without a visible window, audio, or persistent test data

## Test Steps

- Case 1 (configuration): Declare PyInstaller, the module entry point, windowed one-folder spec,
  and deterministic output name.
- Case 2 (smoke mode): Compose and close the runtime under an isolated directory without showing
  the main window.
- Case 3 (override): Honor `SMT_GUARD_DATA_DIR` for packaged diagnostics.
- Case 4 (documentation): Provide build and packaged smoke-test commands.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
