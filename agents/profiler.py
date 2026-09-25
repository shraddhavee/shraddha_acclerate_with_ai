from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import settings


def _column_profile(series: pd.Series) -> dict[str, Any]:
    non_null = series.dropna()
    result: dict[str, Any] = {
        "dtype": str(series.dtype),
        "row_count": int(len(series)),
        "null_count": int(series.isna().sum()),
        "null_fraction": round(float(series.isna().mean()), 4),
        "unique_count": int(series.nunique(dropna=True)),
        "sample_values": [str(value) for value in non_null.head(5).tolist()],
    }
    if pd.api.types.is_numeric_dtype(series):
        result["numeric_statistics"] = {
            "min": float(non_null.min()) if not non_null.empty else None,
            "max": float(non_null.max()) if not non_null.empty else None,
            "mean": float(non_null.mean()) if not non_null.empty else None,
            "median": float(non_null.median()) if not non_null.empty else None,
        }
    return result


def profile_csv(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.suffix.lower() != ".csv":
        raise ValueError(f"Expected a CSV file: {path}")
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    columns = {column: _column_profile(frame[column]) for column in frame.columns}
    issues = []
    for column, profile in columns.items():
        if profile["null_fraction"] > 0:
            issues.append({"column": column, "issue": "nulls_present", "severity": "warning"})
        if profile["unique_count"] <= 1:
            issues.append({"column": column, "issue": "constant_or_empty", "severity": "warning"})
        if frame[column].dtype == "object" and frame[column].astype(str).str.len().max() > 500:
            issues.append({"column": column, "issue": "long_text", "severity": "info"})
    likely_keys = [
        column for column in frame.columns
        if frame[column].nunique(dropna=True) == len(frame) and frame[column].notna().all()
    ]
    return {
        "file": str(path),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": columns,
        "quality_issues": issues,
        "likely_join_keys": likely_keys,
        "sample_rows": frame.head(5).fillna("").to_dict(orient="records"),
    }


def profile_files(paths: list[str | Path], output_path: str | Path | None = None) -> dict[str, Any]:
    profile = {"files": [profile_csv(path) for path in paths]}
    output = Path(output_path) if output_path else settings.data_dir / "profiles" / "profile.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")
    return profile
