# Step 1 - Understand Intent

## Functional Requirements

### FR-13: Manage devices and stations in a PySide6 screen

Provide a reusable PySide6 widget that lists devices, creates devices, selects the active device,
lists its stations, creates one station or a formatted station range, disables devices and
stations, and deletes unreferenced stations. User-visible success and domain-error feedback must
be shown without blocking the workflow.

## Assumptions

- The first application version uses disable operations instead of physically deleting devices.
- Station deletion follows the existing rule: referenced stations cannot be deleted.
- The screen is a reusable widget that a main application window can host in a later composition
  cycle.
- Lists are sorted by code for predictable operation.
- Automated GUI tests instantiate widgets with Qt's `offscreen` platform and never call `show()`.
- Modal message boxes are avoided because scanner-oriented workflows should not require mouse
  dismissal and they make unattended tests unsafe.
