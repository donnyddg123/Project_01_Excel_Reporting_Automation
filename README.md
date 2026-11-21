# Project 01 — Excel Reporting Automation V1.0


Python program for consolidating three sales Excel files, standardizing fields, validating data, calculating revenue, retaining and flagging duplicates, and producing three Excel reports.


## Confirmed business rules
- `Unit Cost` in source C is treated as sales unit price and maps to `unit_price`.
- Duplicate records are retained, flagged, and included in summary calculations.
- Missing or invalid quantity/price prevents revenue calculation (revenue remains blank).
- Original inputs are read-only; the pipeline hashes inputs before/after.
- Output is written to a timestamped run folder. A folder collision fails safely instead of overwriting.

## Outputs
1. `cleaned_sales.xlsx`: standardized 9-column sales detail.
2. `summary_by_region.xlsx`: row count, unique order count, quantity, revenue, valid revenue row count, average revenue per unique order.
3. `data_quality_issues.xlsx`: issue-by-issue log with source file, source row, order ID, field, issue, raw value, suggested action.

## Requirements
Python 3.10+ recommended.

```bash
python -m pip install -r requirements.txt
```


## Run
From the project folder:
```bash
python src/sales_automation.py
```
Outputs are written under `output/run_YYYYMMDD_HHMMSS/`; logs are in `logs/`.


## Test
```bash
pytest -q
```
Tests cover source reading, standardized columns, revenue calculation, missing values, duplicate detection, summary inclusion of all rows, input integrity, output creation, and collision safety.


## Data quality rules
- Missing ID/product/region: retain row and flag.
- Missing/unparseable date: retain row and flag.
- Missing/non-numeric quantity or price: retain row and flag; revenue blank.
- Quantity <= 0 or price < 0: retain and flag; revenue blank.
- Repeated order ID: flag `DUPLICATE_ORDER_ID`.
- Exact duplicate business record: flag `DUPLICATE_ROW`.
- Multiple flags can appear together in `data_status`.


## Notes
Revenue is calculated as quantity × unit price. The summary includes every retained record, including duplicate records, as confirmed by the user. In summary, `unique_order_count` counts distinct order IDs; `record_count` counts all retained rows. Revenue sums ignore missing revenue values.
