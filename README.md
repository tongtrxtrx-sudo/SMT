# SMT Guard

SMT Guard is an offline Windows desktop application for verifying that the material reel
loaded at a placement-machine station matches the material required by the active product
configuration.

## MVP capabilities

- Configure devices and physical stations.
- Record the current operator once per application session and attribute all subsequent changes,
  imports, production runs, and audits to that operator.
- Follow a guided BOM -> station table -> validation and activation import flow.
- Scan device, station, and material codes in a controlled sequence.
- Compare material codes exactly while preserving leading zeroes.
- Show clear OK or NG feedback and production progress.
- Persist device/station lifecycle, versioned BOMs, product configurations, production runs,
  station progress, append-only verification attempts, and critical-change audit logs in SQLite.
- Review and export run records as UTF-8 CSV.
- Manage versioned BOMs and product configurations through draft, release, activation, disable/
  obsolete, and archive lifecycles.
- Query production-run snapshots and station progress, resume interrupted runs, and filter the
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

Application data is stored in `%LOCALAPPDATA%\SMTGuard\smt_guard.sqlite3` by default.

## Persistence foundation

The database is upgraded by ordered, checksummed forward migrations recorded in
`schema_migrations`; startup rejects unknown future versions or modified migration history.
Released BOM and configuration versions are immutable, while changes are created as new versions.
Only active configurations whose current devices and stations remain enabled are offered to the
scan page. Production-run headers and configuration snapshots are written before the first scan,
so zero-scan and interrupted runs remain queryable and recoverable through the repository layer.

The desktop UI exposes eight focused pages grouped as work, configuration, and system tasks, with
scanning as the first page. After confirmation, the shared operator editor collapses to the current
identity and a deliberate switch action. Write actions are rejected until a non-empty operator
identifier is confirmed.

## Product lifecycle workflow

1. Confirm the current operator in the bar above the page tabs.
2. Use **设备与站位** to search, edit, enable, disable, delete unreferenced master data, or archive
   referenced data. Archived state is displayed separately from ordinary disabled state.
3. Import a BOM. For a changed BOM whose previous version already exists, fill **BOM 新版本** so
   the change is stored as another draft instead of modifying released details in place.
4. Use **配置 · BOM** to compare compact version summaries, then inspect materials and provenance
   (source filename, SHA-256, import time, and operator) in the detail pane before enabling or
   disabling a version.
5. Use **产品配置** to copy a released configuration into a new draft, add/remove/edit station
   assignments, validate it, and publish/activate/disable/archive it. Released assignment details
   are immutable. The scan page lists only active, non-empty configurations whose referenced
   devices and stations are still enabled.
6. Start work on **作业 · 扫码**. A run header and configuration snapshot are persisted before the
   first scan. The page keeps one large current-step prompt visible, accepts scanner Enter directly,
   reports scanner focus, and keeps recent history collapsed. Starting another run, changing
   operator, or closing the application interrupts an unfinished run. **作业 · 生产运行** can filter
   runs in a compact six-column list, show full time/interruption details beside it, display the last
   query time, inspect station progress and scan records, export the selected run as CSV, and return
   an interrupted run to scanning for recovery. A run completes automatically after the final
   required station receives an OK verification.
7. Use **系统 · 审计日志** to filter immutable history by entity type/key, operator, action, and a
   calendar date-time range. **今天**, **近 7 天**, and **近 30 天** apply common ranges directly.
   Scan attempts and audit entries cannot be edited or deleted.

## Import workflow

1. Create and enable the required devices and stations on the master-data page.
2. On **配置 · 导入配置**, complete step 1 by selecting and importing a BOM. The page shows the
   product, BOM version, and material count, then advances to step 2 automatically.
3. Select the station table, enter its worksheet name and product version, and review the parsed
   station count.
4. In step 3, verify the combined summary and choose **校验并启用**. Validation errors remain on the
   page so they can be corrected without losing the current workflow context.

After restarting the application, import the BOM again before importing another station table.
The supplied template is `templates\站位表导入模板.xlsx`. Its `Worksheet` sheet uses the required
columns `设备编码`, `站位编码`, and `物料编码`; replace or delete the example row before use and keep
all codes as text to preserve leading zeroes.

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
