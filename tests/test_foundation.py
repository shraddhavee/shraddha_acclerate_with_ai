from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from agents.profiler import profile_csv, profile_files
from agents.sttm_generator import generate_sttm
from core.audit import audit_event
from core.config import settings
from core.memory import LocalMemory
from core.observability import trace_step
from core.state import PipelineState


def test_repository_data_folders_exist():
    settings.ensure_directories()
    for name in ("bronze", "silver", "gold", "sttm", "profiles", "reports", "traces"):
        assert (settings.data_dir / name).is_dir()


def test_state_audit_trace_and_memory_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = PipelineState(run_id="smoke", business_intent="Review retail sales")
    state_path = tmp_path / "nested" / "state.json"
    state.save(state_path)
    assert PipelineState.load(state_path).to_dict() == state.to_dict()

    audit_root = tmp_path / "traces"
    audit_event("smoke", "manual_check", {"rows": 3}, audit_root)
    with trace_step("smoke", "profile"):
        pass
    records = [json.loads(line) for line in (Path("data/traces") / "smoke.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(record["event"] == "step_completed" for record in records)

    memory = LocalMemory(tmp_path / "memory.json")
    memory.remember("smoke", {"intent": state.business_intent})
    assert memory.read()["smoke"]["intent"] == state.business_intent


def test_synthetic_csv_profile_and_bronze_sttm(tmp_path):
    source = tmp_path / "synthetic_sales.csv"
    pd.DataFrame(
        {
            "order_id": ["SYN-1", "SYN-2", "SYN-3"],
            "product": ["Canvas Tote", "Steel Bottle", "Canvas Tote"],
            "quantity": [2, 1, 3],
            "sales_amount": [36.0, 24.0, 54.0],
        }
    ).to_csv(source, index=False)
    profile = profile_csv(source)
    assert profile["row_count"] == 3
    assert profile["columns"]["sales_amount"]["numeric_statistics"]["max"] == 54.0
    profile_path = tmp_path / "profile.json"
    profile_bundle = profile_files([source], profile_path)

    sttm_path = tmp_path / "bronze_sttm.csv"
    sttm = generate_sttm(profile_bundle, "bronze", sttm_path)
    assert sttm_path.exists()
    assert list(sttm.columns) == [
        "source_file", "source_column", "target_column", "transformation_logic",
        "datatype", "nullable", "business_rule", "approval_status",
    ]
    assert set(sttm["approval_status"]) == {"pending"}
    assert set(sttm["source_column"]) == {"order_id", "product", "quantity", "sales_amount"}


def test_profiler_and_sttm_reject_invalid_inputs(tmp_path):
    with pytest.raises(FileNotFoundError):
        profile_csv(tmp_path / "missing.csv")
    with pytest.raises(ValueError, match="Unsupported STTM layer"):
        generate_sttm({"files": []}, "platinum", tmp_path / "sttm.csv")