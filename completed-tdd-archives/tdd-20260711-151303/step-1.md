# Step 1 - Understand Intent

## Functional Requirements

### FR-19: Compose the persistent desktop application

Create an application runtime that initializes one SQLite database file, composes device/station,
configuration import, scanning, and record-query widgets in a navigable main window, shares the
same repositories across pages, refreshes scan configurations after a successful import, and
closes the window and database safely and idempotently.

### FR-20: Provide Windows runtime adapters and entry point

Resolve a stable per-user application-data directory, generate readable unique run identifiers,
map abstract OK/NG tones to Windows `MessageBeep`, and expose a `smt-guard` project script that
creates and shows the composed application.

## Assumptions

- Production data is stored at `%LOCALAPPDATA%\SMTGuard\smt_guard.sqlite3`.
- If `LOCALAPPDATA` is unavailable, the Windows home `AppData\Local\SMTGuard` path is used.
- Run identifiers contain local UTC timestamp text plus an eight-character random token.
- OK uses the standard Windows OK beep and NG uses the Windows hand/error beep.
- The main navigation uses tabs in the order scan, device/station, import, and records.
- Automated tests create the database under `TemporaryDirectory`, inject fake audio and fixed
  identifiers, instantiate Qt offscreen, and never invoke the visible `main()` entry point.
