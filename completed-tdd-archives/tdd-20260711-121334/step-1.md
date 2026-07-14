# Step 1 - Understand Intent

## Functional Requirements

### FR-16: Record and report a verification run

Coordinate the ordered scan state machine, operator feedback, fixed run identity, timestamps, and
append-only attempt repository. Record every accepted material verification, preserve NG retries,
mark checks after an already completed station as repeated, and increment progress only once per
station.

### FR-17: Operate scanning from a PySide6 screen

List persisted product configurations, start a selected run, accept scanner keyboard input in the
device-station-material order, show the required next scan, render OK/NG feedback, expected and
scanned materials, progress, and current-run attempt history.

### FR-18: Query and export verification records

Provide a PySide6 record screen that queries attempts by exact run identifier, displays complete
history in identifier order, and exports the selected run through the existing UTF-8 CSV exporter.

## Assumptions

- Scanner input is keyboard-wedge input terminated by Enter; no serial-port integration is used.
- A run identifier is generated when the operator starts a configuration and remains fixed for
  that run.
- Repeated means a material check performed after the same device/station has already achieved OK
  in the current run. An NG followed by the first OK is not repeated.
- Rejected device or station scans are feedback events but not material verification attempts.
- Exact run-id filtering is sufficient for the first record-query screen.
- Real audio playback remains behind the existing `AudioSink`; automated tests use a fake sink.
- GUI tests use Qt offscreen, SQLite or repositories in memory, fixed clocks, and temporary export
  paths only.
