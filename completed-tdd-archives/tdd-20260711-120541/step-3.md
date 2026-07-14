# Step 3 - Write Failing Test

## Failing Tests Created

- FR-14: Import and persist a validated product configuration -
  `docs/scenario/configuration_import_workflow.md` -
  `tests/scenario/test_configuration_import_workflow.py`
- FR-15: Import BOM and station tables in a PySide6 screen -
  `docs/scenario/configuration_import_ui.md` -
  `tests/scenario/test_configuration_import_ui.py`

RED verification failed during collection with `ModuleNotFoundError: smt_guard.importing`,
confirming that neither the workflow nor its UI existed.
