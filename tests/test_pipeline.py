from pathlib import Path

import pandas as pd

from agents.orchestrator import approve_bronze, approve_gold, approve_silver, new_state, profile_and_prepare


def test_pipeline_without_llm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for directory in ("data/bronze", "data/silver", "data/gold", "data/sttm", "data/profiles", "data/reports", "data/traces"):
        Path(directory).mkdir(parents=True)
    source = tmp_path / "sales.csv"
    pd.DataFrame({"order_id": ["a", "b", "b"], "product": [" A ", "B", "B"], "order_date": ["2026-01-01", "2026-01-02", "2026-01-02"], "sales_amount": [10, 20, 20]}).to_csv(source, index=False)
    state = profile_and_prepare(new_state([str(source)], "Review sales"))
    assert state.status == "awaiting_bronze_approval"
    state = approve_bronze(state)
    assert state.status == "awaiting_silver_approval"
    state = approve_silver(state)
    assert state.status == "awaiting_gold_approval"
    state = approve_gold(state)
    assert state.status == "completed"
    assert Path(state.report_path).exists()
