# SMT Guard

SMT Guard is an offline Windows desktop application for verifying that the material reel
loaded at a placement-machine station matches the material required by the active product
configuration.

## MVP capabilities

- Configure devices and physical stations.
- Restore the last confirmed operator at startup and attribute all subsequent changes, imports,
  production runs, and audits to that operator until an explicit switch.
- Import and activate a product configuration directly from one station/material workbook.
- Enforce globally unique station codes and scan station then material; the owning device is
  resolved automatically while remaining available in records and exports.
- Compare material codes exactly while preserving leading zeroes.
- Show clear OK or NG feedback and production progress.
- Persist device/station lifecycle, versioned BOMs, product configurations, production runs,
  station progress, append-only verification attempts, and critical-change audit logs in SQLite.
- Review and export run records as UTF-8 CSV.
- Keep historical BOM rows readable for compatibility while excluding BOM management from the
  normal operator workflow.
- Query job snapshots and station progress, resume interrupted jobs, and filter the
  append-only audit log.

Learning mode, fuzzy material matching, brand substitution, networking, PLC integration, and
conveyor control are outside the MVP.

## Project structure

- `src/smt_guard/`: application package
- `tests/scenario/`: acceptance-oriented business tests
- `docs/scenario/`: Given-When-Then scenario documents
- `tdd-summary/`: active TDD step reports

## Development

The project uses Python 3.13 and uv. Dependencies are declared in `pyproject.toml` but are not
installed during the initial RED test phase.

After dependencies are approved and synchronized:

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run pyright
```

## Run

Start the desktop application from the synchronized project environment:

```powershell
uv run smt-guard
```

The production window starts maximized. The scan page keeps one vertical reading order: a bounded
current-task card, large scanner input, compact single-row progress, and a full-width attempt table.
The attempt table is shown by default at full-screen widths and collapsed in a medium window.
Management tables and detail panes also share available width responsively, while the import guide
remains centered at a readable maximum width.

Application data is stored in `%LOCALAPPDATA%\SMTGuard\smt_guard.sqlite3` by default.
The last operator is stored beside it in `last_operator.txt`, and user-adjusted table columns and
split-pane proportions are stored in `ui_layout.json` so the next launch restores the same view.

## Persistence foundation

The database is upgraded by ordered, checksummed forward migrations recorded in
`schema_migrations`; startup rejects unknown future versions or modified migration history.
Released configuration versions are immutable, while changes are created as new versions. Legacy
BOM data remains readable but is no longer required by normal imports or scanning.
Only active configurations whose current devices and stations remain enabled are offered to the
scan page. Production-run headers and configuration snapshots are written before the first scan,
so zero-scan and interrupted runs remain queryable and recoverable through the repository layer.

The everyday navigation exposes `扫码作业`, `作业记录`, `设备与站位`, `产品配置`, and `更多`, with
scanning as the first page. After confirmation, the compact lower-left operator control shows the
current identity and a deliberate switch action. The confirmed identity is restored from the
application data directory on the next startup. Write actions are rejected until a non-empty
operator identifier is confirmed.

## Product lifecycle workflow

1. Confirm or switch the current operator in the lower-left sidebar control.
2. Use **设备与站位** to search, edit, enable, disable, delete unreferenced master data, or archive
   referenced data. Archived state is displayed separately from ordinary disabled state.
3. In **产品配置**, choose **导入新配置**, enter the product code and configuration version, select
   a two-column station/material workbook, and choose **导入并使用**. The owning device is resolved
   from each globally unique station code and the validated configuration is activated immediately.
4. Use **产品配置** to copy an active configuration into a new draft, add/remove/edit station and
   material assignments, then **保存并校验** before activation. Active assignment details are
   immutable. The scan page lists only active, non-empty configurations whose referenced devices
   and stations are still enabled.
5. Start work on **扫码作业**. A job header and configuration snapshot are persisted before the
   first scan. The page keeps one large current-step prompt visible, accepts scanner Enter directly,
   reports scanner focus, and shows recent history by default. Starting another job, changing
   operator, or closing the application interrupts an unfinished job. **作业记录** can filter jobs
   in a compact five-column list, show full time/interruption details beside it, inspect station
   progress and scan records, export the selected job as CSV, and return an interrupted job to
   scanning for recovery. A job completes automatically after the final
   required station receives an OK verification.
6. Use **更多 · 审计日志** to filter immutable history by entity type/key, operator, action, and a
   calendar date-time range. **今天**, **近 7 天**, and **近 30 天** apply common ranges directly.
   Scan attempts and audit entries cannot be edited or deleted.

## Import workflow

1. Create and enable the required devices and stations on the master-data page.
2. On **产品配置**, choose **导入新配置**, fill in `产品编码` and `配置版本`, and select the worksheet.
3. Import an Excel sheet whose required columns are `站位编码` and `物料编码`, then choose
   **导入并使用**. Validation feedback stays on the same page.

Use **下载模板** on the import page or the supplied `templates\站位表导入模板.xlsx`. Replace or
delete the example row and keep all codes as text to preserve leading zeroes. Existing three-column
files containing `设备编码` remain supported; when supplied, the device must match the station's
actual owner.

## Windows build

Build the windowed one-folder distribution from the project root:

```powershell
.\scripts\build_windows.ps1
```

The executable is produced at `dist\SMTGuard\SMTGuard.exe`, with the station-table template copied
to the same folder. Verify packaged startup without
showing a window or playing audio by directing its SQLite file to a disposable directory:

```powershell
$env:SMT_GUARD_DATA_DIR = "$env:TEMP\SMTGuard-Smoke"
.\dist\SMTGuard\SMTGuard.exe --smoke-test
```

For validation without overwriting an existing untracked `build` or `dist`, invoke PyInstaller
directly with separate `--workpath` and `--distpath` directories and copy the template into that
isolated distribution before running the same smoke test.

## Safety

Automated tests use temporary files, in-memory databases, and fake audio adapters. They do not
connect to production equipment, launch the GUI, or access external services.
