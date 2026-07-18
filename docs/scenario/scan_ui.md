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
- Case 6 (history): Give recent attempts the full page width and show them by default at
  full-screen width; keep them collapsed in a medium window until the operator expands them.
- Case 7 (manual fallback): Keep a smaller manual-submit action for keyboard diagnostics.
- Case 8 (empty state): Disable unavailable start controls and provide a direct import action.
- Case 9 (scan input): Keep the scanner input at least 56 pixels high with readable 18-pixel text.
- Case 10 (space allocation): Limit the full-screen task card to 400 pixels, render progress as a
  single row no taller than 72 pixels, and let the scan-record table use the remaining height.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
