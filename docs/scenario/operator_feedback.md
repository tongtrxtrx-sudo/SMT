# Scenario: Clear operator feedback

- Given: The application is waiting for or has just processed a scan
- When: The scan state or verification result changes
- Then: The view model exposes clear text, color intent, progress, and an audio event

## Test Steps

- Case 1 (waiting state): Show that the system is waiting for a station or material.
- Case 2 (OK): Expose a green OK state with expected and scanned material codes.
- Case 3 (NG): Expose a red NG state with expected and scanned material codes.
- Case 4 (progress): Increase completed-station progress only after an OK result.
- Case 5 (audio boundary): Emit an abstract OK or NG audio event without playing real audio in tests.
- Case 6 (complete): Show completion when every required station has at least one OK result.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
