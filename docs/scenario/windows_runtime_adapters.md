# Scenario: Provide Windows runtime adapters and entry point

- Given: Windows environment values, clock/token sources, and a beep boundary
- When: The application resolves storage, creates run IDs, or emits feedback tones
- Then: Stable local paths, unique readable IDs, and correct Windows beep kinds are produced

## Test Steps

- Case 1 (data path): Resolve `LOCALAPPDATA` and a deterministic home fallback.
- Case 2 (run IDs): Include timestamp and normalized unique token text.
- Case 3 (audio): Map OK and NG to distinct expected beep values through an injected function.
- Case 4 (entry point): Declare the `smt-guard` project script without executing a GUI in tests.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
