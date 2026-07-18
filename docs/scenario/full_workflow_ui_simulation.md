# Scenario: Simulate the complete eight-page shop-floor workflow

- Given: A fresh application data directory, a confirmed operator, and real BOM/station Excel files
- When: The operator creates master data, imports configuration, scans material, queries and exports
  records, maintains lifecycle data, and reviews the audit log
- Then: Every page completes its real repository-backed action without losing context or corrupting data

## Workflow

1. Confirm `OP-E2E` and create one device plus one station from the device/station page.
2. Generate real `.xlsx` fixtures with `openpyxl`, import the BOM, review the station sheet, and enable
   the resulting product configuration.
3. Start a production run and submit device, station, one wrong material, and the expected material
   through the same Qt controls used by a scanner sending Enter.
4. Open production-run details, verify the NG and OK records, and export the selected run to CSV.
5. Query the same run from record search and export it again through the advanced-query workflow.
6. Update the device, disable and re-enable its station, then exercise BOM and product-configuration
   lifecycle actions.
7. Query the current operator's audit trail, visit all eight composed pages, and finish with SQLite
   `PRAGMA integrity_check`.

## Automated Evidence

The scenario is implemented by
`ApplicationCompositionTests.test_complete_eight_page_workflow_uses_real_database_and_workbooks`.
It uses the production application composition, SQLite repositories, Excel readers, Qt buttons and
line edits, scanner-style Enter events, and both CSV export paths; mocks are limited to choosing the
destination path for the native save-file dialog.
