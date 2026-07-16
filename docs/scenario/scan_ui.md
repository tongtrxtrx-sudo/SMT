# Scenario: Operate scanning from a PySide6 screen

- Given: Persisted product configurations and the scanning screen
- When: An operator selects a configuration, starts a run, and scans codes followed by Enter
- Then: The screen keeps the current task visually dominant, advances prompts, and stores attempts

## Test Steps

- Case 1 (configuration): Load configurations and start a deterministic run.
- Case 2 (current task): Use a large blue/orange/green prompt for device, station, and material.
- Case 3 (scanner focus): Auto-submit on Enter, restore focus, and show ready/unfocused status.
- Case 4 (OK flow): Process device-station-material and show a large green result panel.
- Case 5 (NG flow): Show a large red result panel, expected/scanned material, and retain the step.
- Case 6 (history): Keep recent attempts collapsed until the operator expands them.
- Case 7 (manual fallback): Keep a smaller manual-submit action for keyboard diagnostics.
- Case 8 (empty state): Disable unavailable start controls and provide a direct import action.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
