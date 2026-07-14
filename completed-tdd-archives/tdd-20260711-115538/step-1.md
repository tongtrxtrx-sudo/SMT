# Step 1 - Understand Intent

## Functional Requirements

### FR-10: Initialize the SQLite database safely

Create the application schema idempotently on a supplied SQLite connection, enable foreign-key
enforcement, and record a schema version. The schema must cover devices, stations, versioned
product configurations, station assignments, and immutable verification attempts.

### FR-11: Persist device and station master data

Provide a SQLite-backed master-data service with the same code normalization, uniqueness,
enable/disable, bulk station creation, station reference, and protected deletion behavior as the
existing in-memory service. Data must remain available to another service using the same database.

### FR-12: Persist configurations and append-only attempts

Save and reload versioned product configurations and their device/station/material assignments.
Append complete verification attempts with deterministic identifiers and query them by run in
identifier order. Repositories must not expose update or delete operations for attempts.

## Assumptions

- Database connections are created by application composition and injected into repositories.
- The first schema version is `1`; later schema changes will require explicit migrations.
- Saving an existing product/version configuration is rejected rather than silently replacing it.
- Product configurations have already passed BOM and station validation before persistence.
- Timestamps are stored as timezone-preserving ISO 8601 text.
- Automated tests use SQLite `:memory:` only; the production database path is selected by the GUI
  application in a later cycle.
