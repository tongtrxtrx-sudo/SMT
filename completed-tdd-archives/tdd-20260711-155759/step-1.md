# Step 1 - Understand Intent

## Functional Requirements

### FR-23: Guarantee readable operator UI and scanner focus

Apply an explicit light Windows UI theme with Chinese-capable font fallbacks and non-black table
surfaces. When a run starts, and whenever the operator returns to the scan tab, focus must move to
the scanner input so keyboard-wedge scans do not enter the wrong control.

## Assumptions

- Font order is `Microsoft YaHei UI`, `Microsoft YaHei`, then `Segoe UI`.
- The theme uses explicit white input/table surfaces and dark text independent of OS dark mode.
- Scanner focus is restored only when an active run has enabled the input.
- Visual verification continues with offscreen screenshots; visible hardware validation remains a
  separate final step.
