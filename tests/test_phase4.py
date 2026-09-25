from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from agents.orchestrator import approve_bronze, approve_gold, approve_silver, new_state, profile_and_prepare
from agents.reporter import create_report
from core.config import Settings


def test_reporter_runs_duckdb_and_writes_plotly_html(tmp_path):
    gold = tmp_path / "gold.parquet"
    pd.DataFrame(
        {
            "record_id": ["r1", "r2"],
            "product": ["Canvas Tote", "Steel Bottle"],
            "sales_amount": [36.0, 24.0],
            "source_count": [1, 1],
        }
    ).to_parquet(gold, index=False)
    report = tmp_path / "reports" / "executive.html"

    result = create_report([str(gold)], report, "Approved synthetic retail evidence.")

    assert result == str(report)
    body = report.read_text(encoding="utf-8")
    assert "Approved synthetic retail evidence." in body
    assert "Approved Gold records:" in body
    assert "Distribution of sales_amount" in body
    assert "plotly" in body.lower()
    assert "36.0" in body


def test_report_includes_business_intent_scope(tmp_path):
    gold = tmp_path / "gold.parquet"
    pd.DataFrame({"record_id": ["r1"], "sales_amount": [36.0], "source_count": [1]}).to_parquet(gold, index=False)
    report = tmp_path / "reports" / "scoped.html"

    create_report([str(gold)], report, "Narrative", "Review product performance")

    assert "Analysis scope" in report.read_text(encoding="utf-8")
    assert "Review product performance" in report.read_text(encoding="utf-8")


def test_complete_synthetic_pipeline_writes_gold_report_and_trace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline_settings = Settings(root_dir=tmp_path)
    pipeline_settings.ensure_directories()
    import agents.orchestrator as orchestrator
    monkeypatch.setattr(orchestrator, "settings", pipeline_settings)

    source = tmp_path / "synthetic_sales.csv"
    pd.DataFrame(
        {
            "order_id": ["SYN-001", "SYN-002"],
            "product": ["Canvas Tote", "Steel Bottle"],
            "order_date": ["2026-01-05", "2026-01-06"],
            "quantity": [2, 1],
            "sales_amount": [36.0, 24.0],
            "synthetic_source": [True, True],
        }
    ).to_csv(source, index=False)

    state = profile_and_prepare(new_state([str(source)], "Review synthetic sales"))
    state = approve_bronze(state)
    state = approve_silver(state)
    state = approve_gold(state)

    assert state.status == "completed"
    assert state.gold_output_paths
    assert all(Path(path).exists() for path in state.gold_output_paths)
    assert state.report_path and Path(state.report_path).parent.name == "reports"
    assert Path(state.report_path).exists()
    trace = Path("data/traces") / f"{state.run_id}.jsonl"
    assert trace.exists()
    events = [json.loads(line)["event"] for line in trace.read_text(encoding="utf-8").splitlines()]
    assert "step_completed" in events
    assert "step_failed" not in events
    serialized = trace.read_text(encoding="utf-8")
    assert "GROQ_API_KEY" not in serialized
    assert "gsk_" not in serialized
