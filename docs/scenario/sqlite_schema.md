# Scenario: Initialize the SQLite database safely

- Given: A new or already initialized SQLite connection
- When: The application initializes its database
- Then: Versioned tables and foreign-key enforcement are ready without destructive changes

## Test Steps

- Case 1 (fresh database): Create every required table, indexes, and schema version.
- Case 2 (idempotency): Initialize the same connection twice without losing existing data.
- Case 3 (integrity): Reject station rows whose device does not exist.
- Case 4 (upgrade): Upgrade a legacy v1 database to the lifecycle schema without losing data.
- Case 5 (atomicity): Roll back a failed migration without advancing history or `user_version`.
- Case 6 (compatibility): Reject databases created by a newer application schema.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
