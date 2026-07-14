# Step 3 - Write Failing Test

## Failing Tests Created

- FR-23: Guarantee readable operator UI and scanner focus -
  `docs/scenario/operator_ui_readiness.md` -
  `tests/scenario/test_operator_ui_readiness.py`

Initial RED verification produced the expected theme and focus failures. Later visual acceptance
exposed transparent table viewports, and the added viewport regression test failed across all five
tables before the opaque light-surface implementation was added.
