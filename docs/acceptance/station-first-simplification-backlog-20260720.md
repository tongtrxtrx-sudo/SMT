# Station-first simplification backlog

Date: 2026-07-20
Status: Implementation in progress. The core station-first workflow and the first laptop UX pass
were implemented on 2026-07-20; the remaining items below are explicitly tracked as follow-up work.

## Implementation progress (2026-07-20)

Completed in the current implementation pass:

- Removed BOM management and the separate import wizard from normal navigation while preserving
  historical BOM tables and repositories for compatibility.
- Added a one-screen `导入产品配置` flow, two-column workbook support, legacy three-column support,
  automatic device resolution, Chinese validation feedback, and a downloadable two-column template.
- Made a successful direct import active immediately so the configuration can be selected for
  scanning without a separate publish/activate step.
- Reduced configuration editing to station/material columns and automatic device resolution.
- Added persisted, daily sequential short job numbers while retaining the immutable internal run ID
  in storage, tooltips, audit data, and exports.
- Simplified the scan page, fixed the idle progress state and clipped hero area, expanded recent
  attempts, hid device/repeat columns by default, shortened same-day timestamps, hid manual submit,
  and added explicit station rescan.
- Reduced everyday navigation, moved audit/layout controls under `更多`, moved operator switching to
  the lower-left control, and removed the normal diagnostic strip.
- Simplified job/configuration tables, made state actions contextual, hid the station `已引用` column,
  collapsed custom date/time inputs, and added narrow-window vertical list/detail reflow.
- Localized audit actions, actors, entity/field names, and readable before/after values while keeping
  raw JSON behind `查看原始数据`.
- Completed a realistic-data pass on the unlocked Windows desktop at `1440x850` for scan, job,
  device/station, configuration, and audit/settings pages. The scan history keeps the device column
  hidden after saved-layout restoration, shows duplicate information only when needed, and labels
  its default expanded state as `收起`. The follow-up pass also ensured restored table columns refill
  the available width, short job numbers remain visible, list timestamps are compact, and audit
  `station_count` is shown as `站位数`.
- Verified the implementation with 197 automated tests plus 51 subtests, Ruff, Pyright, bytecode
  compilation, SQLite `quick_check`, and migration-4/job-number integrity checks.

Still deferred after this pass:

- Physically deleting dormant BOM code or database tables. This remains intentionally out of scope
  until historical-data and backup/restore compatibility receive separate approval.
- Replacing narrow-window stacked panes with a dedicated detail drawer/view. The current vertical
  reflow is an intermediate responsive solution.
- Replacing every persistent feedback strip with timed notifications and adding confirmation dialogs
  for each destructive state change.
- Manual visual verification at every remaining scaling/data combination in the laptop acceptance
  matrix; the completed `1440x850` desktop pass does not replace the 125%/150%, long-value, and
  100-row combinations below.

## Context

Station codes are now required to be globally unique across all devices. The scanner workflow can
therefore resolve the owning device from a station code while retaining `device_code` internally for
configuration integrity, production history, auditability, and exports.

The operator-facing workflow should contain only the concepts needed for scan verification. BOM
management does not participate in the actual station/material comparison and has been confirmed as
unnecessary for this operation. Long technical run identifiers are also useful for internal
traceability but are too prominent for daily shop-floor communication.

## Confirmed target workflow

The daily workflow should be reduced to:

`维护设备和站位 -> 导入产品配置 -> 开始扫码 -> 查看生产作业`

- A product configuration is identified by `产品编码` and `配置版本`.
- Its import workbook contains only `站位编码` and `物料编码`.
- The owning device is resolved automatically from the globally unique station code.
- BOM import, BOM lifecycle management, and BOM material-membership checks are not part of the
  operator workflow.
- Operators see a short `作业号`; the existing full run identifier remains available internally for
  traceability.

## Recommended scope

### Priority 1: remove BOM from the operating workflow

- Remove `BOM 管理` from the main navigation.
- Replace the current `导入 BOM -> 导入站位表 -> 校验并启用` wizard with one
  `导入产品配置` workflow.
- Ask for `产品编码` and `配置版本` directly on the import page instead of deriving the product from
  a BOM workbook.
- Do not require product name, product specification, BOM number, BOM version, material name,
  material specification, quantity, or category for scan verification.
- Do not validate imported material codes against BOM items. Continue validating that a material
  code is present and non-empty.
- Remove BOM fields from product-configuration and production-run screens.
- Remove BOM publish, activate, obsolete, archive, history comparison, source file, and SHA-256
  controls from the operator-facing application.
- Create new configurations with no BOM association.
- Keep existing BOM tables, imported BOM rows, and historical configuration references in the
  database for compatibility. Do not physically delete historical BOM data as part of this change.
- Stop reading or displaying historical BOM data in normal workflows. A later schema-cleanup pass
  may remove dormant BOM code only after backup/restore and historical-data compatibility are
  separately verified.

### Priority 2: simplify configuration input

- Accept a two-column station workbook containing `站位编码` and `物料编码`.
- Resolve `设备编码` from station master data during validation and persistence.
- Continue accepting the existing three-column workbook for backward compatibility.
- When an old workbook supplies `设备编码`, reject the row if it does not match the station's actual
  owning device.
- Update the generated workbook template and help text to explain both accepted formats.
- Require a non-empty product code and configuration version on the import page.
- Reject a duplicate product/configuration version with a clear Chinese message.
- Require at least one valid station/material assignment.
- Import and activate the validated product configuration in one operator action.

### Priority 3: simplify configuration editing

- Let users edit station and material codes only.
- Resolve and store the owning device automatically.
- Display the resolved device as read-only context when useful, rather than as a required editable
  field.
- Detect duplicate station codes by station code alone.
- Remove BOM selectors and BOM metadata from the configuration editor and configuration list.

### Priority 4: simplify the scanning screen

- Hide the device column by default in the recent-scan table to give station and material columns
  more width on laptop screens.
- Keep device information in production-run details, audit data, persisted attempts, and CSV exports.
- After a station scan, show confirmation such as `当前站位 F-01 · 所属设备 SMT-01`.
- Add an explicit `重新扫描站位` action for correcting a selected station while waiting for a
  material scan. Do not silently treat an arbitrary material scan as a station switch because the
  two code namespaces may overlap.

### Priority 5: introduce a short operator-facing job number

- Rename the operator-facing label `运行号` to `作业号` where it describes one production scan job.
- Display a short daily sequence such as `0720-003` in the scanning page, production-run list, and
  production-run summary.
- Keep the existing identifier such as `RUN-20260720-101856-XXXXXXXX` as the immutable internal
  `run_id`; do not rewrite historical attempts, run states, audit rows, or foreign-key relationships.
- Persist an explicit short job number rather than relying on visual truncation of the full run ID.
- Allocate the daily sequence atomically in SQLite so restarting the application cannot reuse a job
  number.
- Keep the full internal run ID available in run details, tooltips, audit data, and CSV exports.
- Export both `作业号` and `内部运行编号` so a short number used in 现场沟通 can still be traced to the
  exact persisted run.
- Give historical runs a stable short display number without changing their original `run_id`.

### Priority 6: internal cleanup

- Remove obsolete device-first scan helpers after confirming they have no external callers.
- Centralize global station resolution so imports, configuration editing, and scanning share the
  same validation behavior and error messages.
- Remove BOM-dependent application services and UI wiring only after the direct configuration
  import path is covered by tests.
- Keep legacy BOM persistence readable until a separate, explicitly approved database migration
  removes it.
- Centralize short job-number allocation and formatting instead of deriving display strings in
  individual widgets.

## Additional laptop UX simplification review

These recommendations were recorded after reviewing every current application page at laptop-sized
window widths as well as the maximized layout. They extend the confirmed station-first, BOM-free,
and short-job-number direction above. They are recommendations for a future implementation pass and
do not change business data or behavior by themselves.

The primary layout problem is not the global font size. Too many concepts, low-frequency controls,
and fixed-height regions are shown at the same time, while narrow windows continue to use compressed
side-by-side panes. Preserve readable Chinese text and solve the problem through information
hierarchy, responsive reflow, contextual actions, and removal of duplicated content.

### UX Priority 0: correct misleading or unsafe interface states

- Show an empty grey progress bar when the scan count is `0 / 0`. Do not use an indeterminate green
  progress animation before a job has started.
- Remove conflicting fixed minimum and maximum heights from the scanning hero and recent-attempt
  regions. The central prompt must never be vertically clipped after resizing the window or
  expanding recent records.
- When the selected device changes, clear the station editor before refreshing the station list.
  Populate station fields only from a station selected under the current device, so stale station
  codes from the previous device cannot be edited or saved accidentally.
- Before saving a station, verify again that it belongs to the currently selected device.
- Localize every audit action and system actor shown to users, including `DELETE`, `ARCHIVE`, and
  `SYSTEM_MIGRATION`.
- Render audit changes as readable Chinese field/value differences. Keep raw JSON available only
  behind a collapsed `查看原始数据` action.

### UX Priority 1: reduce the main navigation and persistent chrome

- Reduce the everyday navigation to `扫码作业`, `作业记录`, `产品配置`, and `设备与站位`.
- Rename `生产运行` to `作业记录` so the page matches the operator-facing `作业号` terminology.
- Move configuration import into `产品配置` as a prominent `导入新配置` action instead of keeping a
  separate navigation destination.
- Move `审计日志` into a lower-frequency `设置` or `更多` destination.
- Keep the operator control in the lower-left sidebar, but present the current operator and
  `切换操作员` action as one compact block.
- Remove the persistent full-width diagnostic bar from ordinary pages. Show database, voice, or
  scanner diagnostics only when something is abnormal; put normal diagnostic details in settings.
- Move `恢复默认布局` into settings and rename it to the more explicit
  `重置表格列宽和分栏`.
- Replace permanent `就绪` and success strips with short-lived notifications. Display validation
  errors next to the field or operation that caused them.

### UX Priority 2: make the scanning page task-focused

- Before a job starts, show one compact setup row containing the product configuration selector and
  one primary `开始作业` button. Do not repeat the selected product and `未开始` state in multiple
  headings and empty-state cards.
- After the job starts, lock the selected configuration and replace the setup explanation with the
  short job number, progress, and one large dynamic next-step prompt.
- Use task prompts such as `请扫描站位码` and, after station resolution,
  `当前站位 F-01 · 所属设备 SMT-01` followed by `请扫描物料码`.
- Keep the central prompt compact, approximately 160 to 200 logical pixels high on a laptop. Give
  the recent-attempt table the remaining vertical space.
- Show the latest five to eight attempts by default without requiring an expand operation when
  space is available.
- Use recent-attempt columns `时间`, `站位`, `要求物料`, `扫码物料`, and `结果`. Hide the device
  column by default and show duplicate information only when a duplicate actually occurs.
- For attempts made today, show `HH:mm:ss` instead of repeating the full date on every row.
- Hide `手动提交` in normal scanner operation. Expose it through an explicit supervisor or
  `手动输入模式` when keyboard debugging is required.
- Use both text and color for scan results. An NG message must clearly state the expected and
  scanned material codes without blocking the next scan longer than necessary.

### UX Priority 3: reflow management pages instead of squeezing columns

- On wide screens, management pages may retain a list/detail split. On narrow laptop content widths,
  show the list at full width and open the selected record in a detail drawer or dedicated detail
  view instead of compressing two panes side by side.
- Apply the reflow to `作业记录` and `产品配置`; do not rely only on smaller columns, horizontal
  scrolling, or saved splitter ratios.
- In the job list, show `作业号`, `产品 / 配置版本`, `状态`, `进度`, and `开始时间` by default.
  Move operator, full internal run ID, end time, interruption details, and traceability data into the
  selected job details.
- Simplify the default job filter to one keyword field, status, and a date preset such as `近 7 天`.
  Expand explicit start/end timestamps only after the user selects a custom date range.
- Remove `转到扫码开始` from the job filter because the main navigation already provides that route.
- Keep `恢复作业`, `导出 CSV`, and `中断作业` with the selected job details and show only actions
  valid for the selected state.
- Keep one route to scan records; do not show both a scan-record tab and a duplicate
  `查看扫码记录` button.

### UX Priority 4: simplify configuration and master-data editing

- After BOM removal, use configuration-list columns `产品编码`, `配置版本`, `状态`, `站位数`, and
  `更新时间`.
- In configuration details, make `站位编码` and `物料编码` the primary editable values. Display the
  resolved owning device only as read-only context when useful.
- Provide one primary action per configuration state. A draft exposes station-row editing and
  `保存并校验`; an active or historical version is read-only and primarily exposes
  `复制为新版本`.
- Run configuration validation automatically during save or import instead of requiring a separate
  lifecycle button for ordinary use.
- Import a new configuration on one screen: product code, configuration version, one workbook,
  validation summary, and one `导入并使用` action. Keep template download and detailed validation
  errors available without restoring a multi-step wizard.
- Give device and station maintenance explicit view, create, and edit modes. Do not show create,
  save, enable, and disable as equally prominent simultaneous actions.
- For an enabled object show only the applicable `停用` action; for a disabled object show only
  `启用`.
- Keep batch station creation as a lower-frequency expandable or `更多操作` action.
- Hide the low-frequency `已引用` station column by default. Treat station name as optional and
  visually secondary if production does not depend on it.
- When a globally unique station code conflicts, identify the owning device in the error, for
  example `站位 F-01 已属于设备 SMT-01`.

### UX Priority 5: establish a restrained visual and interaction system

- Do not reduce the application font globally to make content fit. Target 14 to 16 logical pixels
  for body, table, and button text; solve density through fewer visible fields and responsive layout.
- Use one blue primary button per task area. Use neutral outline styling for secondary actions and
  reserve destructive styling for the currently selected object.
- Reduce nested pale cards and borders. Prefer one main white content surface with headings and
  subtle dividers; use cards only for summaries or states that benefit from grouping.
- Hide permanently unavailable actions. If an action is only temporarily disabled, explain the
  reason close to the control.
- Preserve readable table row heights of approximately 36 to 40 logical pixels and prioritize
  columns instead of shrinking every column to its minimum width.
- Use status text as well as color so state remains understandable for users with reduced color
  perception.
- Preserve keyboard scanner behavior and visible input focus. Add ordinary keyboard conveniences
  such as `Ctrl+F` for the current page filter and `Esc` to cancel or clear only where they are safe.
- Require concise, object-specific confirmation for state-changing operations such as interrupting
  a job or disabling a device/configuration. Do not add confirmation dialogs to ordinary search and
  save operations.
- Preserve the selected row after refresh whenever that object still exists.
- Use action-oriented empty states, for example `还没有可用的产品配置` with one
  `导入产品配置` action, instead of a large blank panel.

### Laptop visual acceptance matrix

- Verify maximized and ordinary-window layouts at `1366x768` with Windows 125% display scaling.
- Verify maximized and ordinary-window layouts at `1440x850` with Windows 125% and 150% display
  scaling.
- Verify each page with empty data, realistic data, long product/material/station values, and at
  least 100 table rows.
- Verify scan states `未开始`, `等待站位`, `等待物料`, `正确`, `NG`, `已完成`, and `已中断`.
- Verify that resizing between a large monitor and a laptop does not leave a clipped prompt, stale
  splitter proportion, unusable saved column width, or hidden primary action.
- Verify that recent attempts show at least five readable rows when the laptop height allows it.
- Verify that operational tables avoid horizontal scrolling for their default columns. Horizontal
  scrolling remains acceptable for advanced audit or export-oriented data.
- Verify that every truncated value remains available through the selected-record details or a
  tooltip without making the primary workflow depend on hover.
- Verify scanner `Enter` submission, automatic scan-input focus after navigation, explicit station
  rescan, and recovery from NG without a mouse.
- Verify that destructive state changes identify the affected object and consequence before
  confirmation.

## Compatibility and non-goals

- Do not remove devices or the device-to-station ownership relationship from master data.
- Do not remove `device_code` from product assignments, run snapshots, attempt records, audit logs,
  or exports.
- Do not replace existing composite keys solely for presentation simplification; that migration has
  high risk and little operator-facing benefit.
- Do not silently merge, rename, or delete legacy stations when a uniqueness conflict is found.
- Do not drop BOM tables or delete imported BOM data during the operator-workflow simplification.
- Do not remove or shorten the existing internal `run_id`; it remains the durable technical key.
- Do not make the short job number the only value available to audit and export functions.

## Acceptance criteria

- A new two-column workbook imports successfully when every station exists, is enabled, and maps to
  exactly one enabled device.
- The import page accepts `产品编码`, `配置版本`, and one two-column station/material workbook without
  asking for a BOM file.
- Existing three-column workbooks continue to import without modification.
- A mismatched device/station pair in an old workbook is rejected with the source row number.
- A blank material code, duplicate station code, unknown/disabled station, empty configuration, or
  duplicate product/configuration version is rejected with a clear Chinese message.
- A material code that has never appeared in a BOM can still be imported and verified by scanning.
- `BOM 管理` and BOM lifecycle actions are absent from the normal navigation and import workflow.
- Existing configurations and production history that reference historical BOM rows remain readable
  after the UI no longer exposes BOM data.
- Configuration editing persists the same internal `(device_code, station_code) -> material_code`
  assignment after the device column is removed from editable input.
- The scanning page shows station and material as the only operator scan steps.
- The current station and automatically resolved device are visible before material verification.
- New production runs receive a short, unique, sequential daily `作业号` while preserving the full
  internal `run_id`.
- Restarting the application and starting another run does not reuse an existing short job number.
- Run details, audit data, and CSV exports can map every short job number back to exactly one full
  internal run ID.
- Historical runs display stable short job numbers without modifying their stored full IDs.
- Recent scan records fit better on a 1366x768 or 1440x850 laptop screen while full traceability is
  preserved in run details and CSV exports.
- Unit, in-memory SQLite integration, migration, import compatibility, backup/restore compatibility,
  CSV export, and offscreen Qt tests cover the new and legacy paths.
