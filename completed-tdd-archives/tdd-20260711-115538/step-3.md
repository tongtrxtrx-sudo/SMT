# Step 3 - Write Failing Test

## Failing Tests Created

- FR-10: Initialize the SQLite database safely - `docs/scenario/sqlite_schema.md` -
  `tests/scenario/test_sqlite_schema.py`
- FR-11: Persist device and station master data - `docs/scenario/sqlite_master_data.md` -
  `tests/scenario/test_sqlite_master_data.py`
- FR-12: Persist configurations and append-only attempts -
  `docs/scenario/sqlite_configuration_records.md` -
  `tests/scenario/test_sqlite_configuration_records.py`

RED verification failed during collection with `ModuleNotFoundError: smt_guard.sqlite` for all
three files, confirming the persistence implementation did not exist.
