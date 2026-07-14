# Step 3 - Write Failing Test

## Failing Tests Created

- FR-24: Import BOM and station tables as separate actions -
  `docs/scenario/separate_bom_station_import.md` -
  `tests/scenario/test_separate_bom_station_import.py`
- FR-25: Provide a station-table Excel template -
  `docs/scenario/station_table_template.md` -
  `tests/scenario/test_station_table_template.py`

RED verification produced eight expected failures: the separate service methods and UI buttons did
not exist, the template workbook did not exist, and the Windows build did not copy the template.
