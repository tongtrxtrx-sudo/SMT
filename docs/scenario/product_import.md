# Scenario: Product configuration import

- Given: Enabled devices and stations exist in the system
- When: The operator imports the supplied `.xlsx` BOM and a product station table
- Then: A versioned product configuration is created using material codes as text

## Test Steps

- Case 1 (happy path): Import the `Worksheet` sheet and map `商品编号`, `商品名`, `商品规格`, `单位用量`, and `商品分类`.
- Case 2 (leading zero): Preserve `013000081` exactly as text.
- Case 3 (finished product): Use the row with `深度=0` to identify the finished product.
- Case 4 (component rows): Treat rows with `深度>0` as candidate component materials.
- Case 5 (non-SMT material): Allow a BOM item to remain unused when it does not appear in the station table.

## Status

- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
