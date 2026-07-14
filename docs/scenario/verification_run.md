# Scenario: Record and report a verification run

- Given: A product configuration, run identity, clock, feedback controller, and attempt repository
- When: Device, station, and material codes are scanned
- Then: Ordered feedback and immutable material attempts are produced with correct progress

## Test Steps

- Case 1 (happy path): Record a complete OK attempt with run and configuration identity.
- Case 2 (retry): Preserve NG followed by OK and increment progress only on OK.
- Case 3 (repeat): Mark checks after station completion as repeated without double progress.
- Case 4 (rejected order): Do not create an attempt for rejected device or station scans.
- Case 5 (write failure): Restore scanner state when the immutable attempt cannot be stored.
- Case 6 (multi-device): Switch devices inside one configuration without restarting the run.
- Case 7 (recovery): Persist, interrupt, query, and resume runs even when no scans exist.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
