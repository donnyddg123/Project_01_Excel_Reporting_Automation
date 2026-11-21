from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Iterable


import pandas as pd


STANDARD_COLUMNS = [
    "order_id", "order_date", "product", "quantity", "unit_price",
    "revenue", "region", "source_file", "data_status",
]
ALIASES = {
    "order_id": ["Order ID", "order_id", "Order Number"],
    "order_date": ["Order Date", "date", "Date"],
    "product": ["Product", "item", "Product Name"],
    "quantity": ["Qty", "quantity", "Units"],
    "unit_price": ["Unit Price", "price_each", "Unit Cost"],
    "region": ["Region", "sales_region", "Area"],
}



def _norm_col(value: object) -> str:
    return str(value).strip().lower()



def _pick_column(df: pd.DataFrame, standard: str, source_file: str) -> str:
    lookup = {_norm_col(c): c for c in df.columns}
    for alias in ALIASES[standard]:
        if _norm_col(alias) in lookup:
            return lookup[_norm_col(alias)]
    raise ValueError(f"{source_file}: missing required column for '{standard}'. Expected one of {ALIASES[standard]}; got {list(df.columns)}")


def read_and_standardize(file_path: Path) -> pd.DataFrame:
    raw = pd.read_excel(file_path, sheet_name=0)
    out = pd.DataFrame(index=raw.index)
    for field in ALIASES:
        col = _pick_column(raw, field, file_path.name)
        out[field] = raw[col]
    out["source_file"] = file_path.name
    out["_source_row"] = raw.index + 2  # Excel row numbers, header assumed row 1
    out["_raw_record"] = raw.astype(object).where(pd.notna(raw), None).to_dict(orient="records")
    return out


def _flag(existing: list[str], flag: str) -> list[str]:
    if flag not in existing:
        existing.append(flag)
    return existing


def clean_and_validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = df.copy()
    issues: list[dict] = []
    data["order_id"] = data["order_id"].astype("string").str.strip()
    data["product"] = data["product"].astype("string").str.strip()
    data["region"] = data["region"].astype("string").str.strip()
    data["order_date"] = pd.to_datetime(data["order_date"], errors="coerce", format="mixed")
    data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")
    data["unit_price"] = pd.to_numeric(data["unit_price"], errors="coerce")
    statuses: list[list[str]] = [[] for _ in range(len(data))]

    def issue(i: int, field: str, reason: str, raw_value: object, suggested: str, flag: str) -> None:
        statuses[i].append(flag)
        issues.append({
            "source_file": data.iloc[i]["source_file"],
            "source_row": int(data.iloc[i]["_source_row"]),
            "order_id": data.iloc[i]["order_id"],
            "field": field,
            "issue_reason": reason,
            "raw_value": raw_value,
            "suggested_action": suggested,
        })

    for i in range(len(data)):
        row = data.iloc[i]
        if pd.isna(row["order_id"]) or str(row["order_id"]).strip() == "":
            issue(i, "order_id", "Missing order ID", None, "Check source record and assign an ID if appropriate", "MISSING_ORDER_ID")
        if pd.isna(row["order_date"]):
            issue(i, "order_date", "Date is missing or cannot be parsed", row.get("order_date"), "Correct the date in the source", "INVALID_DATE")
        if pd.isna(row["product"]) or str(row["product"]).strip() == "":
            issue(i, "product", "Missing product", None, "Fill product name from source", "MISSING_PRODUCT")
        if pd.isna(row["quantity"]):
            issue(i, "quantity", "Missing or non-numeric quantity", row.get("quantity"), "Confirm quantity from source; revenue remains blank", "MISSING_QUANTITY")
        elif row["quantity"] <= 0:
            issue(i, "quantity", "Quantity must be positive", row["quantity"], "Verify quantity; revenue remains blank", "INVALID_QUANTITY")
        if pd.isna(row["unit_price"]):
            issue(i, "unit_price", "Missing or non-numeric unit price", row.get("unit_price"), "Confirm unit price from source", "MISSING_UNIT_PRICE")
        elif row["unit_price"] < 0:
            issue(i, "unit_price", "Unit price cannot be negative", row["unit_price"], "Verify unit price; revenue remains blank", "INVALID_UNIT_PRICE")
        if pd.isna(row["region"]) or str(row["region"]).strip() == "":
            issue(i, "region", "Missing region", None, "Fill region from source", "MISSING_REGION")

    # Exact duplicate rows (excluding source metadata) are retained and flagged.
    duplicate_mask = data["order_id"].duplicated(keep=False)
    for i in range(len(data)):
        if duplicate_mask.iloc[i]:
            issue(i, "order_id", "Order ID appears more than once", data.iloc[i]["order_id"], "Review duplicate order IDs; all records are retained", "DUPLICATE_ORDER_ID")
    business_cols = ["order_id", "order_date", "product", "quantity", "unit_price", "region"]
    exact_duplicate_mask = data[business_cols].duplicated(keep=False)
    for i in range(len(data)):
        if exact_duplicate_mask.iloc[i]:
            issue(i, "record", "Exact duplicate business record", data.iloc[i]["_raw_record"], "Review duplicate row; all records are retained and included in totals", "DUPLICATE_ROW")

    data["revenue"] = data["quantity"] * data["unit_price"]
    invalid_revenue = data["quantity"].isna() | (data["quantity"] <= 0) | data["unit_price"].isna() | (data["unit_price"] < 0)
    data.loc[invalid_revenue, "revenue"] = pd.NA
    data["data_status"] = ["OK" if not s else ";".join(sorted(set(s))) for s in statuses]
    data["order_date"] = data["order_date"].dt.date
    details = data[STANDARD_COLUMNS].copy()
    details["quantity"] = details["quantity"].astype("Float64")
    details["unit_price"] = details["unit_price"].astype("Float64")
    details["revenue"] = details["revenue"].astype("Float64")
    issues_df = pd.DataFrame(issues, columns=["source_file", "source_row", "order_id", "field", "issue_reason", "raw_value", "suggested_action"])
    return details, issues_df


def make_summary(details: pd.DataFrame) -> pd.DataFrame:
    # All records, including duplicate records, are included as confirmed by user.
    working = details.copy()
    working["revenue"] = pd.to_numeric(working["revenue"], errors="coerce")
    working["quantity"] = pd.to_numeric(working["quantity"], errors="coerce")
    summary = working.groupby("region", dropna=False).agg(
        record_count=("order_id", "size"),
        unique_order_count=("order_id", "nunique"),
        total_quantity=("quantity", "sum"),
        total_revenue=("revenue", "sum"),
        valid_revenue_records=("revenue", "count"),
    ).reset_index()
    summary["average_revenue_per_unique_order"] = summary["total_revenue"] / summary["unique_order_count"].replace(0, pd.NA)
    return summary.sort_values("region", na_position="last").reset_index(drop=True)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_pipeline(input_dir: Path, output_dir: Path, log_dir: Path, timestamp: str | None = None) -> dict[str, Path]:
    input_dir, output_dir, log_dir = input_dir.resolve(), output_dir.resolve(), log_dir.resolve()
    files = sorted(input_dir.glob("sales_source_*.xlsx"))
    if len(files) != 3:
        raise FileNotFoundError(f"Expected exactly 3 sales_source_*.xlsx files in {input_dir}; found {len(files)}")
    before_hashes = {p: file_sha256(p) for p in files}
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)  # fail safely; never overwrite a prior run
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{timestamp}.log"
    logger = logging.getLogger(f"sales_automation_{timestamp}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

    try:
        frames = [read_and_standardize(p) for p in files]
        combined = pd.concat(frames, ignore_index=True)
        details, issues = clean_and_validate(combined)
        summary = make_summary(details)
        paths = {
            "cleaned_sales": run_dir / "cleaned_sales.xlsx",
            "summary_by_region": run_dir / "summary_by_region.xlsx",
            "data_quality_issues": run_dir / "data_quality_issues.xlsx",
        }
        with pd.ExcelWriter(paths["cleaned_sales"], engine="openpyxl") as writer:
            details.to_excel(writer, sheet_name="Cleaned Sales", index=False)
            writer.sheets["Cleaned Sales"].freeze_panes = "A2"
            writer.sheets["Cleaned Sales"].auto_filter.ref = writer.sheets["Cleaned Sales"].dimensions
        with pd.ExcelWriter(paths["summary_by_region"], engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="Regional Summary", index=False)
            writer.sheets["Regional Summary"].freeze_panes = "A2"
            writer.sheets["Regional Summary"].auto_filter.ref = writer.sheets["Regional Summary"].dimensions
        with pd.ExcelWriter(paths["data_quality_issues"], engine="openpyxl") as writer:
            issues.to_excel(writer, sheet_name="Issues", index=False)
            writer.sheets["Issues"].freeze_panes = "A2"
            if not issues.empty:
                writer.sheets["Issues"].auto_filter.ref = writer.sheets["Issues"].dimensions
        after_hashes = {p: file_sha256(p) for p in files}
        if before_hashes != after_hashes:
            raise RuntimeError("Input file integrity check failed: original input file changed")
        logger.info("Success: rows=%d issues=%d", len(details), len(issues))
        logger.info("Outputs: %s", paths)
        return paths
    except Exception:
        logger.exception("Pipeline failed")
        raise
    finally:
        for h in list(logger.handlers):
            h.close()
            logger.removeHandler(h)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge, clean, validate and summarize 3 sales Excel files.")
    parser.add_argument("--input", default="input", help="Input directory")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument("--logs", default="logs", help="Log directory")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    paths = run_pipeline(project_root / args.input, project_root / args.output, project_root / args.logs)
    print("Completed successfully:")
    for key, path in paths.items():
        print(f"{key}: {path}")


if __name__ == "__main__":
    main()
