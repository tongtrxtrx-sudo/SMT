# Step 3 - Write Failing Test

## Failing Tests Created

- FR-1: Device and station master data - `docs/scenario/device_station_master.md` - `tests/scenario/test_device_station_master.py`
- FR-2: Product configuration import - `docs/scenario/product_import.md` - `tests/scenario/test_product_import.py`
- FR-3: Import validation - `docs/scenario/import_validation.md` - `tests/scenario/test_import_validation.py`
- FR-4: Ordered scan workflow - `docs/scenario/ordered_scan.md` - `tests/scenario/test_ordered_scan.py`
- FR-5: Exact material verification - `docs/scenario/exact_verification.md` - `tests/scenario/test_exact_verification.py`
- FR-6: Clear operator feedback - `docs/scenario/operator_feedback.md` - `tests/scenario/test_operator_feedback.py`
- FR-7: Append-only scan records - `docs/scenario/append_only_records.md` - `tests/scenario/test_append_only_records.py`
- FR-8: Result review and export - `docs/scenario/record_export.md` - `tests/scenario/test_record_export.py`

## RED Verification

- Command: `uv run --no-project python -m unittest discover -s tests/scenario -p 'test_*.py' -v`
- Result: Expected failure with 8 import errors because the production modules do not exist yet.
- Unexpected passes: 0
- External services, production files, GUI, audio, and physical devices accessed: No
