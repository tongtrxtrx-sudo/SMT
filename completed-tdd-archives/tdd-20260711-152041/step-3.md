# Step 3 - Write Failing Test

## Failing Tests Created

- FR-21: Build and smoke-test a Windows distribution -
  `docs/scenario/windows_packaging.md` -
  `tests/scenario/test_windows_packaging.py`

RED verification produced four expected failures: missing explicit data-directory override,
missing spec/build script, missing README commands, and no smoke-test arguments on `main()`.
