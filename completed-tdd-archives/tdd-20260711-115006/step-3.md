# Step 3 - Write Failing Test

## Failing Tests Created

- FR-9: Read real Excel worksheets safely -
  `docs/scenario/openpyxl_workbook_reader.md` -
  `tests/scenario/test_openpyxl_workbook_reader.py`

RED verification command:

```powershell
$env:PYTHONPATH = "src"
python -m unittest tests.scenario.test_openpyxl_workbook_reader -v
```

The test module failed to import with `ModuleNotFoundError: smt_guard.xlsx_reader`, confirming
that the production adapter did not exist before implementation.
