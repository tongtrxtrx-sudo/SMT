# Step 1 - Understand Intent

## Functional Requirements

### FR-14: Import and persist a validated product configuration

Orchestrate real `.xlsx` BOM and station-table reading, map the known `Worksheet` BOM, validate
station rows against BOM materials and enabled physical master data, and save the resulting
versioned product configuration. Return a summary suitable for UI preview.

### FR-15: Import BOM and station tables in a PySide6 screen

Provide a reusable PySide6 widget for BOM path, station-table path, station worksheet name, and
product version. It must support file selection, execute the import workflow, preview product and
assignment results, and display validation or persistence errors without modal dialogs.

## Assumptions

- The BOM worksheet remains fixed as `Worksheet` according to the confirmed ERP export.
- The station-table worksheet defaults to `Worksheet` but is editable.
- The first UI version imports `.xlsx` files; CSV support remains outside this cycle.
- Required station-table columns are `设备编码`, `站位编码`, and `物料编码`.
- A configuration version is supplied manually and cannot be blank.
- Product configuration persistence is atomic at the repository boundary; duplicate
  product/version identities are rejected.
- Integration tests create real `.xlsx` files only inside automatically cleaned temporary
  directories; GUI tests inject a fake workflow and remain offscreen.
