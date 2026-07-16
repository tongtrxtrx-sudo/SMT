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

## Test Steps

- Case 1 (record query): Show a compact scan-result table, total/NG/repeat chips, and a centered
  empty state without horizontal scrolling.
- Case 2 (audit): Translate common entity/action codes, keep raw codes in tooltips, and show the
  selected before/after JSON in a side detail card.
- Case 3 (master data): Put device and station lists before editors, show record counts, and keep
  batch station creation collapsed until requested.
- Case 4 (BOM and configuration): Keep lifecycle actions in the selected-item detail card, move
  comparison/copy actions to secondary cards, and hide low-frequency columns.
- Case 5 (runs and import): Use the shared header/card/table rules without disturbing the direct
  run-detail workflow or the three-step import guide.
- Case 6 (real executable): At 1183 x 857, inspect every navigation destination and confirm that
  primary controls are visible, content is not clipped, and compact tables do not scroll sideways.

## Status

- [x] Write scenario document
- [x] Write focused tests for the affected page behaviors
- [x] Implement the shared components and page-specific hierarchy
- [x] Run focused tests and static analysis
- [x] Build and inspect the isolated Windows executable
- [x] Run the final full verification gate
