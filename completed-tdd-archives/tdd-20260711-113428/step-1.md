# Step 1 - Understand Intent

## Functional Requirements

### FR-1: Device and station master data

An administrator can configure physical devices and their stations before production data is imported. A device code is globally unique. A station is uniquely identified by the combination of device code and station code and can be enabled or disabled.

### FR-2: Product configuration import

The operator can create a versioned product configuration and import the supplied `.xlsx` BOM and a station table. The BOM uses `商品编号` as the material code. The station table contains `设备编码`, `站位编码`, and `物料编码`. BOM, station table, and reel barcode use the same material code as the join key.

### FR-3: Import validation

The system validates required columns, duplicate stations, empty material codes, unknown devices or stations, and station material codes that do not exist in the BOM. Invalid data must not become an active production configuration.

### FR-4: Ordered scan workflow

The operator selects an active product configuration and scans a device code, a station code, and a reel material code in that order. Scanner input is handled as keyboard text terminated by Enter.

### FR-5: Exact material verification

The system compares the scanned reel material code with the material code required by the selected device and station. Exact equality produces an OK result; any difference produces an NG result.

### FR-6: Clear operator feedback

The application displays the current scan step, requested material, scanned material, OK or NG result, and overall progress using large, high-contrast text. Audible feedback is emitted through an injected interface so tests never play real system audio.

### FR-7: Append-only scan records

Every verification attempt is recorded with timestamp, product configuration version, device, station, expected material, scanned material, and result. The normal user interface does not provide record editing or deletion.

### FR-8: Result review and export

The operator can review records for the current production run and export them to CSV.

## Assumptions

- The implementation uses Python 3.13, PySide6, SQLite, uv, pytest, Ruff, and Pyright.
- The first version is an offline Windows desktop application.
- BOM, station table, and reel barcode use the same material code, for example `10002345`.
- Material matching is exact after trimming leading and trailing whitespace. Case conversion and fuzzy matching are not performed.
- Device codes are globally unique. Station codes are unique within a device.
- The supplied workbook has one sheet named `Worksheet` and uses `BOM编号`, `BOM名称`, `深度`, `单位用量`, `商品编号`, `商品名`, `商品规格`, and `商品分类` as the relevant columns.
- The BOM row with `深度` equal to `0` identifies the finished product. Rows with `深度` greater than `0` are candidate component materials.
- Material codes are always handled as text so leading zeroes are preserved.
- Not every BOM component must appear in the SMT station table, because the BOM can contain non-SMT materials. Every material referenced by the station table must exist in the BOM.
- The first version supports `.xlsx` BOM import and `.xlsx` or CSV station-table import. Legacy `.xls` is not included.
- The first version does not include learning mode, automatic material recognition, brand substitution, serial-port control, PLC control, networking, or user authentication.
- Tests use in-memory SQLite databases, temporary files, and fake audio output. Tests do not launch the GUI, access production data, or contact external services.
