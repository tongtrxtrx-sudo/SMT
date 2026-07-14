# Scenario: Persist configurations and append-only attempts

- Given: Master data, a versioned configuration, and verification attempts
- When: The SQLite repositories save and query those objects
- Then: Assignments and immutable attempt history round-trip without code changes

## Test Steps

- Case 1 (configuration): Save and reload exact assignments including leading-zero materials.
- Case 2 (configuration identity): Reject duplicate product/version saves and distinguish versions.
- Case 3 (attempt history): Append OK and NG attempts and return them in identifier order.
- Case 4 (append-only API): Expose no update or delete operations for attempts.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
