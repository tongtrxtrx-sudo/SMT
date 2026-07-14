# Scenario: Operate scanning from a PySide6 screen

- Given: Persisted product configurations and the scanning screen
- When: An operator selects a configuration, starts a run, and scans codes followed by Enter
- Then: The screen advances prompts, renders feedback/progress, and shows stored attempts

## Test Steps

- Case 1 (configuration): Load configurations and start a deterministic run.
- Case 2 (OK flow): Process device-station-material and show green progress/history.
- Case 3 (NG flow): Show red expected/scanned feedback and retain the material step.
- Case 4 (empty state): Explain that a configuration must be imported before scanning.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
