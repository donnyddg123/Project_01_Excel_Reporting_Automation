# Project 01 — V1.0 Test & Run Report

- Execution: successful
- Automated tests: **4 passed, 0 failed** (`pytest -q`)
- Input records: 11 (4 from A, 3 from B, 4 from C)
- Records retained: 11
- Duplicate exact rows retained: 2 occurrences of A-1003 (flagged)
- Missing quantity: C-3004 (flagged; revenue blank)
- Total revenue: 762.00
- Total quantity: 91 (valid quantities only)
- Original inputs: SHA-256 checks before/after run matched


## Output run
`output/run_20261121_220534/`

- `cleaned_sales.xlsx`
- `summary_by_region.xlsx`
- `data_quality_issues.xlsx`

## Test coverage
1. Reads all three source workbooks and standardizes columns.
2. Verifies revenue calculations, missing quantity handling, duplicate flags.
3. Verifies regional summary includes all 11 rows and duplicate-inclusive revenue.
4. Verifies source file hashes remain unchanged, output files are created, and run-folder collision does not overwrite existing files.
