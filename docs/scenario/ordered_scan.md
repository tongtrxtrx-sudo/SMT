# Scenario: Ordered scan workflow

- Given: An active product configuration has been selected
- When: Scanner text terminated by Enter is received
- Then: The system accepts device, station, and reel material codes only in the required order

## Test Steps

- Case 1 (happy path): Accept `SMT-01`, then `F-01`, then a material code.
- Case 2 (material first): Reject a material code while waiting for a device code.
- Case 3 (station first): Reject a station code before a device has been selected.
- Case 4 (unknown device): Reject a device not used by the active product configuration.
- Case 5 (wrong-device station): Reject a station that does not belong to the selected device.
- Case 6 (next cycle): After verification, retain the current device and return to the station step for the next feeder.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
