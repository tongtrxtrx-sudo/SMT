# Step 4 - Implement to Make Tests Pass

## Implementations Completed

- FR-16: Added `VerificationRun` in `src/smt_guard/run.py`, with scan coordination, fixed run
  metadata, append-only attempts, retry/repeat semantics, progress, and abstract audio feedback.
- FR-17: Added configuration listing and `ScanWidget` in `src/smt_guard/ui/scanning.py`.
- FR-18: Added `RecordQueryWidget` in `src/smt_guard/ui/records.py` using the existing CSV
  exporter boundary.

GREEN verification executed all 11 focused tests successfully with in-memory repositories,
offscreen Qt, fake audio, fixed time, and temporary CSV output.
