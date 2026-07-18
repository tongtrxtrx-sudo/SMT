# Scenario: Keep every desktop page focused and consistent

- Given: The desktop application is opened at a typical shop-floor window size
- When: An operator moves between work, configuration, and system pages
- Then: Every page presents the current task first, keeps low-frequency details secondary,
  and uses the same visual language for filters, results, actions, feedback, and empty states

## Shared Page Rules

- Start each management page with one title and one plain-language subtitle.
- Group filters, primary results, selected-item details, and secondary actions into separate cards.
- Use blue for the primary next action, green for enable/success, red for stop/interrupt,
  outlined controls for secondary actions, and gray for unavailable actions.
- Keep the most important four to six table columns visible. Put long paths, hashes, raw JSON,
  and other low-frequency data in the selected-item detail area.
- Avoid horizontal scrolling at the acceptance window size. Preserve hidden data in the widget
  model and tooltips where tests or advanced workflows still require it.
- Replace a blank table with an actionable empty state and show counts or outcome chips after a
  query or selection.
- Keep destructive or lifecycle actions visually separate from refresh, compare, and file-choice
  controls.

## Full-Screen Responsive Rules

- Start the packaged application maximized on dedicated shop-floor terminals.
- Keep the scan task, input, progress, and history in one vertical reading order. At page widths of
  1400 pixels or more, cap the task card at 400 pixels, keep progress to one 72-pixel row, and give
  the recent-scan table the full available width and remaining height.
- Below the full-screen breakpoint, shorten the task card and collapse history by default so the
  same workflow remains usable in an 1180 x 760 window.
- Keep the scanner input at least 56 pixels high so operators can identify its active state from a
  normal standing distance.
- Keep selection and filter inputs at readable maximum widths instead of stretching a single input
  across the entire display.
- Let high-value table columns share spare width. Keep status, counts, and other short values
  compact, and do not allocate all spare width to the final column.
- Allow BOM, configuration, run, device/station, and audit split views to expand their detail panes
  on a wide display; do not cap detail panes at fixed narrow widths.
- Center the import workflow and cap it at 1280 pixels so its three-step reading order remains clear
  on a 1920-pixel display.
- Use a light application canvas, white content cards, a small blue title accent, consistent 12-pixel
  card corners, 36-pixel table rows, and alternating table surfaces across all eight pages.
- Present success, neutral, and error feedback as full-width status strips instead of relying on text
  color alone; retain blue, green, and red action semantics throughout management pages.

## Test Steps

- Case 1 (record query): Show a compact scan-result table, total/NG/repeat chips, and a centered
  empty state without horizontal scrolling.
- Case 2 (audit): Translate common entity/action codes, keep raw codes in tooltips, and show the
  selected before/after JSON in a side detail card.
- Case 3 (master data): Put device and station lists before editors, show record counts, and keep
  batch station creation collapsed until requested.
- Case 4 (BOM and configuration): Present BOMs as current/history versions with automatic switching
  and no manual lifecycle buttons. Keep editable configuration lifecycle actions in the selected-item
  detail card, move comparison/copy actions to secondary cards, and hide low-frequency columns.
- Case 5 (runs and import): Use the shared header/card/table rules without disturbing the direct
  run-detail workflow or the three-step import guide.
- Case 6 (real executable): At 1183 x 857, inspect every navigation destination and confirm that
  primary controls are visible, content is not clipped, and compact tables do not scroll sideways.
- Case 7 (responsive sizes): Render all eight pages at 1920 x 1000 and 1180 x 760. Confirm that the
  scan page gives records full width at both sizes, collapses them only in the medium window,
  management details receive useful width, and no primary action overlaps or clips.
- Case 8 (packaged maximized startup): Launch the isolated executable normally and verify that the
  top-level window is maximized, can close normally, and leaves a valid SQLite database.
- Case 9 (complete workflow): Run the repository-backed eight-page workflow described in
  `full_workflow_ui_simulation.md`, including real Excel import, NG/OK scanning, two CSV exports,
  lifecycle actions, audit lookup, and SQLite integrity validation.
- Case 10 (single record entry): Hide the duplicate record-query navigation item while retaining its
  composed page and repository-backed workflow for compatibility; expose routine scan-record review
  and CSV export through Production Runs.

## Status

- [x] Write scenario document
- [x] Write focused tests for the affected page behaviors
- [x] Implement the shared components and page-specific hierarchy
- [x] Run focused tests and static analysis
- [x] Build and inspect the isolated Windows executable
- [x] Run the final full verification gate
