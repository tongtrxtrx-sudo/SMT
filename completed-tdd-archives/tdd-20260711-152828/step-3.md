# Step 3 - Write Failing Test

## Failing Tests Created

- FR-22: Harden file boundaries and release verification -
  `docs/scenario/security_boundaries.md` -
  `tests/scenario/test_security_boundaries.py`

RED verification failed during collection because `WorkbookLimits` and the archive validator did
not exist, before the remaining security cases could run.
