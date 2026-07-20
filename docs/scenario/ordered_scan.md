# Scenario: Ordered scan workflow

- Given: An active product configuration has been selected
- When: Scanner text terminated by Enter is received
- Then: The system accepts globally unique station and reel material codes in the required order,
  and resolves the owning device automatically

## Test Steps

- Case 1 (happy path): Accept `F-01`, resolve its device, then accept its material code.
- Case 2 (material first): Reject a material code while waiting for a station code.
- Case 3 (device scan removed): Reject a device code while waiting for a station code.
- Case 4 (cross-device resolution): Resolve each globally unique station to its owning device.
- Case 5 (NG retry): Retain the current device and station until the material is correct.
- Case 6 (invariant guard): Reject an ambiguous in-memory configuration containing one station
  code under multiple devices.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
