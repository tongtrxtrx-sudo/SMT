# Scenario: Manage devices and stations in a PySide6 screen

- Given: An initialized master-data repository and the management screen
- When: An operator creates, selects, disables, or deletes devices and stations
- Then: The repository and visible tables reflect the operation and clear feedback is displayed

## Test Steps

- Case 1 (device creation): Add a trimmed device and refresh the visible device list.
- Case 2 (validation feedback): Show a duplicate-code error without a modal dialog.
- Case 3 (station creation): Add one station and a formatted station range for the selected device.
- Case 4 (selection): Selecting another device refreshes the station list and device label.
- Case 5 (lifecycle): Disable a device/station and prevent deletion of a referenced station.
- Case 6 (visual hierarchy): Show lists and record counts before editor controls, and keep batch
  station creation collapsed until the user explicitly expands it.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
