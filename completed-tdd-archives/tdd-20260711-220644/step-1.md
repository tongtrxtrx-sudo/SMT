# Step 1 - Understand Intent

## Functional Requirements

### FR-24: Import BOM and station tables as separate actions

Allow the operator to validate and load a BOM without selecting a station table, then import a
station table in a later action using the loaded BOM to validate and persist the product
configuration. Keep the existing combined service entry point for compatibility.

### FR-25: Provide a station-table Excel template

Provide a polished `.xlsx` template with the exact required station columns, leading-zero-safe
example values, concise Chinese instructions, and include the template beside the packaged EXE.

## Assumptions

- A separately imported BOM remains loaded for the lifetime of the running application; after an
  application restart the operator imports the BOM again before importing a station table.
- The station table data worksheet is named `Worksheet` by default.
- The template includes one clearly marked example row that operators replace or delete.
- The existing combined `import_files` service method remains available for compatibility, while
  the production UI uses the separate actions.
