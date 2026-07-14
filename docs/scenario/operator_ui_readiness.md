# Scenario: Guarantee readable operator UI and scanner focus

- Given: The composed Windows main window and an available product configuration
- When: The application renders, a run starts, or the operator returns to the scan tab
- Then: Chinese-capable light styling is applied and scanner input owns keyboard focus

## Test Steps

- Case 1 (theme): Declare Chinese-capable fonts, dark text, and explicit white table/input surfaces.
- Case 1a (viewport): Force every table viewport to paint its white background on all Qt backends.
- Case 2 (font registration): Register the installed Windows YaHei font for headless rendering.
- Case 3 (run start): Focus scanner input immediately after starting a run.
- Case 4 (tab return): Restore scanner focus when navigating back from another page.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
