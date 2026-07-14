# Step 1 - Understand Intent

## Functional Requirements

### FR-22: Harden file boundaries and release verification

Prevent spreadsheet formula execution when exporting untrusted scanned text, reject oversized or
suspicious `.xlsx` ZIP containers before OpenPyXL extraction, prove SQLite run identifiers remain
parameterized, and provide a repeatable PowerShell release-verification script covering tests,
coverage, lint, types, source security, dependency audit, build, and packaged smoke test.

## Assumptions

- CSV cells beginning with `=`, `+`, `-`, `@`, tab, or carriage return are prefixed with an
  apostrophe for Excel-safe display; stored database values remain exact and unchanged.
- Ordinary codes including leading-zero values are exported unchanged.
- Production `.xlsx` limits are 50 MiB compressed, 200 MiB total uncompressed, and a maximum
  per-entry compression ratio of 1000 for non-empty entries.
- Tests use small custom limits and tiny temporary ZIP files rather than allocating large files.
- Dependency audit requires network or a populated vulnerability cache; all other verification
  commands can run offline after synchronization.
