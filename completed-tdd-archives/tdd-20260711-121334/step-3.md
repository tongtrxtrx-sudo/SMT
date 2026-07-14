# Step 3 - Write Failing Test

## Failing Tests Created

- FR-16: Record and report a verification run - `docs/scenario/verification_run.md` -
  `tests/scenario/test_verification_run.py`
- FR-17: Operate scanning from a PySide6 screen - `docs/scenario/scan_ui.md` -
  `tests/scenario/test_scan_ui.py`
- FR-18: Query and export verification records - `docs/scenario/record_query_ui.md` -
  `tests/scenario/test_record_query_ui.py`

RED verification failed during collection because `smt_guard.run`, `smt_guard.ui.scanning`, and
`smt_guard.ui.records` did not exist.
