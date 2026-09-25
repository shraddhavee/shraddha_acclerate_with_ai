from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import agents.orchestrator as orchestrator
from agents.bronze_agent import create_bronze
from agents.sttm_generator import STTM_COLUMNS, generate_sttm, validate_sttm
from core.config import Settings


def _bronze_sttm(path: Path, source: Path, statuses: list[str] | None = None) -> Path:
    statuses = statuses or ["pending", "pending", "pending"]
    frame = pd.DataFrame(
        [
            [str(source), "order_id", "order_id", "copy source value", "object", "false", "Stable order identifier", statuses[0]],
            [str(source), "product", "product", "trim text", "object", "false", "Product label", statuses[1]],
            [str(source), "sales_amount", "sales_amount", "copy source value", "float64", "true", "Sales amount", statuses[2]],
        ],
        columns=STTM_COLUMNS,
    )
    frame.to_csv(path, index=False)
    return path


def test_sttm_validation_rejects_missing_columns_and_unknown_status(tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text("order_id\nSYN-1\n", encoding="utf-8")
    invalid = tmp_path / "invalid.csv"
    pd.DataFrame({"source_file": [str(source)], "approval_status": ["waiting"]}).to_csv(invalid, index=False)

    with pytest.raises(ValueError, match="missing required columns"):
        validate_sttm(invalid)

    complete = _bronze_sttm(tmp_path / "complete.csv", source, ["approved", "waiting", "pending"])
    with pytest.raises(ValueError, match="Invalid STTM approval status"):
        validate_sttm(complete)


def test_bronze_parquet_contains_only_approved_columns(tmp_path):
    source = tmp_path / "sales.csv"
    pd.DataFrame(
        {"order_id": ["SYN-1"], "product": ["Canvas Tote"], "sales_amount": [36.0], "internal_note": ["drop"]}
    ).to_csv(source, index=False)
    sttm = _bronze_sttm(tmp_path / "bronze.csv", source, ["approved", "approved", "pending"])

    outputs = create_bronze([str(source)], sttm, tmp_path / "bronze")
    output = pd.read_parquet(outputs[0])
    assert list(output.columns) == ["order_id", "product"]
    assert output.iloc[0].to_dict() == {"order_id": "SYN-1", "product": "Canvas Tote"}


def test_bronze_approval_gate_generates_silver_sttm_and_resumes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline_settings = Settings(root_dir=tmp_path)
    pipeline_settings.ensure_directories()
    monkeypatch.setattr(orchestrator, "settings", pipeline_settings)

    source = tmp_path / "sales.csv"
    pd.DataFrame({"order_id": ["SYN-1"], "product": ["Canvas Tote"], "sales_amount": [36.0]}).to_csv(source, index=False)
    state = orchestrator.profile_and_prepare(orchestrator.new_state([str(source)], "Review sales"))
    assert state.status == "awaiting_bronze_approval"
    assert state.sttm_bronze_path and Path(state.sttm_bronze_path).exists()
    assert not state.bronze_output_paths

    resumed = orchestrator.resume_state(state.run_id)
    assert resumed.run_id == state.run_id
    assert resumed.status == "awaiting_bronze_approval"

    approved = orchestrator.approve_bronze(resumed)
    assert approved.status == "awaiting_silver_approval"
    assert approved.bronze_output_paths
    assert approved.sttm_silver_path and Path(approved.sttm_silver_path).exists()
    assert Path(approved.bronze_output_paths[0]).exists()
    assert pd.read_parquet(approved.bronze_output_paths[0]).columns.tolist() == [
        "order_id", "product", "sales_amount"
    ]


def test_rejected_bronze_gate_is_persisted_without_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline_settings = Settings(root_dir=tmp_path)
    pipeline_settings.ensure_directories()
    monkeypatch.setattr(orchestrator, "settings", pipeline_settings)

    source = tmp_path / "sales.csv"
    pd.DataFrame({"order_id": ["SYN-1"], "product": ["Canvas Tote"]}).to_csv(source, index=False)
    state = orchestrator.profile_and_prepare(orchestrator.new_state([str(source)], "Reject test"))
    rejected = orchestrator.approve_bronze(state, approved=False)

    assert rejected.status == "bronze_rejected"
    assert not rejected.bronze_output_paths
    assert orchestrator.resume_state(state.run_id).status == "bronze_rejected"
