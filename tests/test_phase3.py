from __future__ import annotations

from pathlib import Path

import pandas as pd

from agents.gold_agent import create_gold
from agents.silver_agent import create_silver
from agents.sttm_generator import STTM_COLUMNS, generate_gold_sttm


def _sttm(path: Path, rows: list[list[str]]) -> Path:
    pd.DataFrame(rows, columns=STTM_COLUMNS + [
        "operation", "aggregation", "group_by", "join_key", "join_type",
        "left_source_file", "right_source_file",
    ]).to_csv(path, index=False)
    return path


def test_silver_cleans_casts_dates_and_deduplicates(tmp_path):
    bronze = tmp_path / "sales.parquet"
    pd.DataFrame(
        {
            "order_id": ["SYN-1", "SYN-1", "SYN-2"],
            "product": [" Canvas Tote ", " Canvas Tote ", "Steel Bottle"],
            "order_date": ["2026-01-01", "2026-01-01", "bad-date"],
            "quantity": ["2", "2", "1"],
        }
    ).to_parquet(bronze, index=False)
    sttm = _sttm(tmp_path / "silver.csv", [
        [str(bronze), "order_id", "order_id", "copy source value", "string", "false", "Identifier", "approved", "select", "", "", "", "", "", ""],
        [str(bronze), "product", "product", "trim text", "string", "false", "Product", "approved", "select", "", "", "", "", "", ""],
        [str(bronze), "order_date", "order_date", "normalize date", "datetime64[ns, UTC]", "true", "Order date", "approved", "select", "", "", "", "", "", ""],
        [str(bronze), "quantity", "quantity", "cast numeric", "int64", "true", "Quantity", "approved", "select", "", "", "", "", "", ""],
    ])

    outputs = create_silver([str(bronze)], str(sttm), tmp_path / "silver")
    result = pd.read_parquet(outputs[0])
    assert len(result) == 2
    assert result["product"].tolist() == ["Canvas Tote", "Steel Bottle"]
    assert str(result["quantity"].dtype) == "Int64"
    assert str(result["order_date"].dtype).startswith("datetime64[ns, UTC]")
    assert pd.isna(result.loc[1, "order_date"])


def test_gold_sttm_and_approved_aggregation_produce_stable_ids(tmp_path):
    silver = tmp_path / "silver.parquet"
    pd.DataFrame({"product": ["Canvas Tote", "Canvas Tote", "Steel Bottle"], "sales_amount": [36.0, 54.0, 24.0]}).to_parquet(silver, index=False)
    generated = generate_gold_sttm([silver], tmp_path / "gold_sttm.csv")
    assert set(generated["approval_status"]) == {"pending"}
    assert set(generated["operation"]) == {"select"}

    sttm = _sttm(tmp_path / "aggregate.csv", [
        [str(silver), "sales_amount", "total_sales", "sum by product", "float64", "false", "Approved product sales total", "approved", "aggregate", "sum", "product", "", "", "", ""],
    ])
    first = create_gold([str(silver)], str(sttm), tmp_path / "gold")
    second = create_gold([str(silver)], str(sttm), tmp_path / "gold_again")
    result = pd.read_parquet(first[0]).sort_values("product").reset_index(drop=True)
    repeat = pd.read_parquet(second[0]).sort_values("product").reset_index(drop=True)
    assert result[["product", "total_sales"]].to_dict("records") == [
        {"product": "Canvas Tote", "total_sales": 90.0},
        {"product": "Steel Bottle", "total_sales": 24.0},
    ]
    assert result["record_id"].tolist() == repeat["record_id"].tolist()


def test_gold_executes_only_explicit_join(tmp_path):
    left = tmp_path / "orders.parquet"
    right = tmp_path / "customers.parquet"
    pd.DataFrame({"customer_id": ["C1"], "sales_amount": [36.0]}).to_parquet(left, index=False)
    pd.DataFrame({"customer_id": ["C1"], "region": ["North"]}).to_parquet(right, index=False)
    rows = [
        [str(left), "customer_id", "customer_id", "approved join key", "string", "false", "Explicit join", "approved", "join", "", "", "customer_id", "inner", str(left), str(right)],
        [str(left), "sales_amount", "sales_amount", "select approved sales", "float64", "false", "Sales", "approved", "select", "", "", "", "", "", ""],
        [str(right), "region", "region", "select approved region", "string", "false", "Region", "approved", "select", "", "", "", "", "", ""],
    ]
    output = create_gold([str(left), str(right)], str(_sttm(tmp_path / "join.csv", rows)), tmp_path / "gold")
    result = pd.read_parquet(output[0])
    assert result[["customer_id", "sales_amount", "region"]].to_dict("records") == [
        {"customer_id": "C1", "sales_amount": 36.0, "region": "North"}
    ]
