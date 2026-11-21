from pathlib import Path
import sys
import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from sales_automation import read_and_standardize, clean_and_validate, make_summary, file_sha256, run_pipeline


PROJECT = Path(__file__).resolve().parents[1]


def inputs():
    return sorted((PROJECT / "input").glob("sales_source_*.xlsx"))


def test_three_sources_read_and_standardize():
    assert len(inputs()) == 3
    frames = [read_and_standardize(p) for p in inputs()]
    assert [len(x) for x in frames] == [4, 3, 4]
    assert all(set(["order_id", "order_date", "product", "quantity", "unit_price", "region"]).issubset(x.columns) for x in frames)


def test_cleaning_revenue_duplicate_and_missing():
    raw = pd.concat([read_and_standardize(p) for p in inputs()], ignore_index=True)
    details, issues = clean_and_validate(raw)
    assert len(details) == 11
    assert details.loc[details.order_id == "A-1001", "revenue"].iloc[0] == pytest.approx(54.0)
    assert details.loc[details.order_id == "C-3001", "revenue"].iloc[0] == pytest.approx(40.0)
    assert pd.isna(details.loc[details.order_id == "C-3004", "revenue"].iloc[0])
    assert "DUPLICATE_ROW" in details.loc[details.order_id == "A-1003", "data_status"].iloc[0]
    assert "MISSING_QUANTITY" in details.loc[details.order_id == "C-3004", "data_status"].iloc[0]
    assert len(issues) >= 2


def test_summary_includes_duplicates_and_region_totals():
    raw = pd.concat([read_and_standardize(p) for p in inputs()], ignore_index=True)
    details, _ = clean_and_validate(raw)
    summary = make_summary(details)
    assert int(summary.record_count.sum()) == 11
    west = summary.loc[summary.region == "West"].iloc[0]
    assert west.record_count == 4
    assert west.total_revenue == pytest.approx(159.0)


def test_input_hashes_unchanged_and_outputs_written(tmp_path):
    files = inputs()
    hashes_before = {p: file_sha256(p) for p in files}
    result = run_pipeline(PROJECT / "input", tmp_path / "output", tmp_path / "logs", timestamp="test_run")
    hashes_after = {p: file_sha256(p) for p in files}
    assert hashes_before == hashes_after
    assert all(p.exists() for p in result.values())
    assert len(pd.read_excel(result["cleaned_sales"])) == 11
    with pytest.raises(FileExistsError):
        run_pipeline(PROJECT / "input", tmp_path / "output", tmp_path / "logs", timestamp="test_run")
