from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import pandas as pd

from agents.bronze_agent import create_bronze
from agents.gold_agent import create_gold
from agents.llm import generate_text, profile_interpretation
from agents.profiler import profile_files
from agents.reporter import create_report
from agents.silver_agent import create_silver
from agents.sttm_generator import generate_gold_sttm, generate_sttm, validate_sttm
from core.audit import audit_event
from core.config import settings
from core.memory import LocalMemory
from core.observability import trace_step
from core.state import PipelineState


def _approve(path: str, approved: bool) -> None:
    frame = validate_sttm(path)
    frame["approval_status"] = "approved" if approved else "rejected"
    frame.to_csv(path, index=False)


def _copy_sttm_source(sttm_path: str, source_paths: list[str]) -> None:
    frame = pd.read_csv(sttm_path)
    source_map = {Path(path).stem: path for path in source_paths}
    frame["source_file"] = frame["source_file"].map(
        lambda value: source_map.get(Path(str(value)).stem, source_paths[0])
    )
    frame.to_csv(sttm_path, index=False)


def new_state(files: list[str], intent: str, task_description: str = "") -> PipelineState:
    return PipelineState(run_id=uuid4().hex, uploaded_files=files, business_intent=intent, task_description=task_description)


def _save_state(state: PipelineState) -> None:
    state.save(settings.data_dir / "traces" / f"{state.run_id}_state.json")


def resume_state(run_id: str) -> PipelineState:
    return PipelineState.load(settings.data_dir / "traces" / f"{run_id}_state.json")


def profile_and_prepare(state: PipelineState) -> PipelineState:
    with trace_step(state.run_id, "profile"):
        profile_path = settings.data_dir / "profiles" / f"{state.run_id}.json"
        profile_files(state.uploaded_files, profile_path)
        state.profile_path = str(profile_path)
        state.sttm_bronze_path = str(settings.data_dir / "sttm" / f"{state.run_id}_bronze.csv")
        import json
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        state.decisions.append(profile_interpretation(profile))
        generate_sttm(profile, "bronze", state.sttm_bronze_path)
        state.status = "awaiting_bronze_approval"
        state.decisions.append("Bronze STTM generated; ambiguous rules remain pending human approval.")
        audit_event(state.run_id, "approval_requested", {"layer": "bronze"})
        _save_state(state)
    return state


def approve_bronze(state: PipelineState, approved: bool = True) -> PipelineState:
    if not state.sttm_bronze_path:
        raise ValueError("Bronze STTM is not available")
    _approve(state.sttm_bronze_path, approved)
    state.approvals["bronze"] = approved
    if not approved:
        state.status = "bronze_rejected"
        state.decisions.append("Bronze STTM rejected; no Bronze output was created.")
        _save_state(state)
        return state
    with trace_step(state.run_id, "bronze"):
        state.bronze_output_paths = create_bronze(state.uploaded_files, state.sttm_bronze_path, settings.data_dir / "bronze")
        import json
        profile = json.loads(Path(state.profile_path).read_text(encoding="utf-8"))
        state.sttm_silver_path = str(settings.data_dir / "sttm" / f"{state.run_id}_silver.csv")
        generate_sttm(profile, "silver", state.sttm_silver_path)
        _copy_sttm_source(state.sttm_silver_path, state.bronze_output_paths)
        state.status = "awaiting_silver_approval"
        state.decisions.append("Bronze Parquet created; Silver STTM awaits approval.")
        _save_state(state)
    return state


def approve_silver(state: PipelineState, approved: bool = True) -> PipelineState:
    if not state.sttm_silver_path:
        raise ValueError("Silver STTM is not available")
    _approve(state.sttm_silver_path, approved)
    state.approvals["silver"] = approved
    if not approved:
        state.status = "silver_rejected"
        state.decisions.append("Silver STTM rejected; no Silver output was created.")
        _save_state(state)
        return state
    with trace_step(state.run_id, "silver"):
        state.silver_output_paths = create_silver(state.bronze_output_paths, state.sttm_silver_path, settings.data_dir / "silver")
        state.sttm_gold_path = str(settings.data_dir / "sttm" / f"{state.run_id}_gold.csv")
        generate_gold_sttm(state.silver_output_paths, state.sttm_gold_path)
        state.status = "awaiting_gold_approval"
        state.decisions.append("Silver Parquet created; Gold STTM awaits approval.")
        _save_state(state)
    return state


def approve_gold(state: PipelineState, approved: bool = True) -> PipelineState:
    if not state.sttm_gold_path:
        raise ValueError("Gold STTM is not available")
    _approve(state.sttm_gold_path, approved)
    state.approvals["gold"] = approved
    if not approved:
        state.status = "gold_rejected"
        return state
    with trace_step(state.run_id, "gold_and_report"):
        state.gold_output_paths = create_gold(state.silver_output_paths, state.sttm_gold_path, settings.data_dir / "gold", state.business_intent)
        report_path = settings.data_dir / "reports" / f"{state.run_id}.html"
        fallback = f"Report for intent: {state.business_intent}. Metrics reflect approved Gold records only."
        narrative = generate_text("Write a concise evidence-based executive narrative for: " + fallback, fallback)
        state.report_path = create_report(state.gold_output_paths, report_path, narrative)
        LocalMemory().remember(state.run_id, {"intent": state.business_intent, "report_path": state.report_path})
        state.status = "completed"
        state.decisions.append("Gold Parquet and executive report created from approved data.")
        _save_state(state)
    return state
