from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


STTM_COLUMNS = [
    "source_file", "source_column", "target_column", "transformation_logic",
    "datatype", "nullable", "business_rule", "approval_status",
]
VALID_APPROVAL_STATUSES = {"pending", "approved", "rejected"}


def _suggestion(source: str, dtype: str, layer: str, key: bool) -> dict[str, Any]:
    target = source.strip().lower().replace(" ", "_")
    logic = "trim text" if dtype == "object" else "copy source value"
    if layer == "silver":
        logic = "trim text; nulls retained unless business-approved otherwise" if dtype == "object" else "cast to inferred datatype"
    if layer == "gold":
        logic = "approved aggregate or join output; confirm business definition"
    return {
        "source_column": source,
        "target_column": target,
        "transformation_logic": logic,
        "datatype": dtype,
        "nullable": "true",
        "business_rule": "Candidate key only; human approval required" if key else "Confirm with business owner",
        "approval_status": "pending",
    }


def generate_sttm(profile: dict[str, Any], layer: str, output_path: str | Path) -> pd.DataFrame:
    if layer not in {"bronze", "silver", "gold"}:
        raise ValueError(f"Unsupported STTM layer: {layer}")
    rows = []
    for file_profile in profile.get("files", []):
        keys = set(file_profile.get("likely_join_keys", []))
        for source, details in file_profile.get("columns", {}).items():
            rows.append({"source_file": file_profile["file"], **_suggestion(source, details["dtype"], layer, source in keys)})
    if layer == "gold" and not rows:
        rows.append({"source_file": "", **_suggestion("business_key", "string", layer, False)})
    frame = pd.DataFrame(rows, columns=STTM_COLUMNS)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return frame


def validate_sttm(
    sttm_path: str | Path,
    expected_source_files: list[str | Path] | None = None,
) -> pd.DataFrame:
    path = Path(sttm_path)
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = [column for column in STTM_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"STTM is missing required columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("STTM must contain at least one mapping row")
    statuses = set(frame["approval_status"].str.lower())
    invalid_statuses = statuses - VALID_APPROVAL_STATUSES
    if invalid_statuses:
        raise ValueError(f"Invalid STTM approval status: {', '.join(sorted(invalid_statuses))}")
    for column in STTM_COLUMNS[:-1]:
        if frame[column].str.strip().eq("").any():
            raise ValueError(f"STTM column contains blank values: {column}")
    if expected_source_files is not None:
        expected = {str(Path(source)) for source in expected_source_files}
        actual = set(frame["source_file"])
        if not actual.issubset(expected):
            raise ValueError("STTM contains a source file outside the uploaded inputs")
    return frame


def approved_columns(sttm_path: str | Path, source_file: str | Path) -> list[str]:
    sttm = validate_sttm(sttm_path)
    source = str(Path(source_file))
    selected = sttm[(sttm["source_file"].astype(str) == source) & (sttm["approval_status"].str.lower() == "approved")]
    return selected["source_column"].tolist()


def approved_mappings(sttm_path: str | Path, source_file: str | Path) -> pd.DataFrame:
    sttm = validate_sttm(sttm_path)
    source = str(Path(source_file))
    return sttm[(sttm["source_file"] == source) & (sttm["approval_status"].str.lower() == "approved")].copy()


def generate_gold_sttm(silver_paths: list[str | Path], output_path: str | Path) -> pd.DataFrame:
    """Generate selectable Gold mappings without guessing joins or measures."""
    rows: list[dict[str, Any]] = []
    for path in silver_paths:
        frame = pd.read_parquet(path, engine="pyarrow")
        for column in frame.columns:
            rows.append({
                "source_file": str(Path(path)),
                "source_column": column,
                "target_column": column,
                "transformation_logic": "select approved Silver column",
                "datatype": str(frame[column].dtype),
                "nullable": str(bool(frame[column].isna().any())).lower(),
                "business_rule": "No inferred join or aggregation; approve explicitly",
                "approval_status": "pending",
                "operation": "select",
                "aggregation": "",
                "group_by": "",
                "join_key": "",
                "join_type": "",
                "left_source_file": "",
                "right_source_file": "",
            })
    frame = pd.DataFrame(rows, columns=STTM_COLUMNS + [
        "operation", "aggregation", "group_by", "join_key", "join_type",
        "left_source_file", "right_source_file",
    ])
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return frame
