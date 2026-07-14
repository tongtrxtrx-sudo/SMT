# Scenario: Persist industrial lifecycle models

- Given: Device/station master data, imported BOMs, product station configurations, and operators
- When: Versions are imported, published, enabled, disabled, obsoleted, or archived
- Then: Identity remains stable, released versions remain immutable, and critical changes are audited

## Test Steps

- Case 1 (BOM provenance): Store source filename, SHA-256, import time, operator, and details.
- Case 2 (BOM immutability): Reject detail changes after publishing or activation.
- Case 3 (configuration lifecycle): Create a draft, publish, activate, disable, and archive it.
- Case 4 (atomic configuration): Roll back assignments and station references on a write failure.
- Case 5 (master-data safety): Hide configurations whose device or station becomes disabled.
- Case 6 (audit): Append create/update/lifecycle events and reject audit update or deletion.
- Case 7 (run atomicity): Store an attempt and station completion in the same transaction.

## Status

- [x] Add regression scenarios before implementation
- [x] Implement ordered SQLite migrations
- [x] Implement persistent lifecycle repositories
- [x] Keep the existing operator UI compatible
- [x] Run focused and full verification
