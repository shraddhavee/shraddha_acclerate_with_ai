from __future__ import annotations

from pathlib import Path
import hashlib
import pandas as pd

from agents.sttm_generator import validate_sttm


def _stable_id(row: pd.Series) -> str:
    payload = "|".join(f"{column}={'' if pd.isna(value) else value}" for column, value in sorted(row.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _load_sources(silver_paths: list[str]) -> dict[str, pd.DataFrame]:
    return {str(Path(path)): pd.read_parquet(path) for path in silver_paths}


def _apply_joins(sources: dict[str, pd.DataFrame], directives: pd.DataFrame) -> pd.DataFrame:
    joined = None
    for _, directive in directives.iterrows():
        left_path = directive["left_source_file"]
        right_path = directive["right_source_file"]
        key = directive["join_key"]
        if left_path not in sources or right_path not in sources:
            raise ValueError("Gold join references an unavailable Silver source")
        if key not in sources[left_path].columns or key not in sources[right_path].columns:
            raise ValueError(f"Gold join key is missing from Silver sources: {key}")
        left = joined if joined is not None else sources[left_path]
        joined = left.merge(sources[right_path], on=key, how=directive["join_type"] or "inner", suffixes=("_left", "_right"))
    return joined if joined is not None else pd.DataFrame()


def _apply_aggregations(frame: pd.DataFrame, mappings: pd.DataFrame) -> pd.DataFrame:
    aggregates = []
    for _, mapping in mappings.iterrows():
        source = mapping["source_column"]
        operation = mapping["aggregation"].lower()
        if source not in frame.columns:
            raise ValueError(f"Gold aggregation column is missing: {source}")
        group_by = [column.strip() for column in mapping.get("group_by", "").split(",") if column.strip()]
        grouped = frame.groupby(group_by, dropna=False)[source] if group_by else frame[source]
        if operation == "sum":
            result = grouped.sum()
        elif operation == "count":
            result = grouped.count()
        elif operation == "mean":
            result = grouped.mean()
        elif operation == "min":
            result = grouped.min()
        elif operation == "max":
            result = grouped.max()
        else:
            raise ValueError(f"Unsupported Gold aggregation: {operation}")
        aggregate = result.reset_index(name=mapping["target_column"]) if group_by else pd.DataFrame({mapping["target_column"]: [result]})
        aggregates.append(aggregate)
    if not aggregates:
        return frame
    result = aggregates[0]
    for aggregate in aggregates[1:]:
        result = result.merge(aggregate, how="outer", left_index=True, right_index=True)
    return result.reset_index(drop=True)


def _operations(frame: pd.DataFrame, operation: str) -> pd.DataFrame:
    if "operation" not in frame.columns:
        return frame if operation == "select" else frame.iloc[0:0]
    return frame[frame["operation"].str.lower() == operation]


def create_gold(silver_paths: list[str], sttm_path: str, output_dir: str | Path, intent: str = "") -> list[str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if not silver_paths:
        raise ValueError("No Silver inputs approved for Gold")
    sttm = validate_sttm(sttm_path, silver_paths)
    approved = sttm[sttm["approval_status"].str.lower() == "approved"]
    if approved.empty:
        raise ValueError("No approved Gold mappings")
    sources = _load_sources(silver_paths)
    join_directives = _operations(approved, "join")
    combined = _apply_joins(sources, join_directives) if not join_directives.empty else pd.concat(sources.values(), ignore_index=True, sort=False)
    selections = _operations(approved, "select") if "operation" in approved else approved
    if not selections.empty:
        columns = selections["source_column"].tolist()
        join_keys = join_directives["join_key"].tolist() if not join_directives.empty else []
        columns = list(dict.fromkeys(join_keys + columns))
        missing = [column for column in columns if column not in combined.columns]
        if missing:
            raise ValueError(f"Approved Gold columns missing from Silver data: {', '.join(missing)}")
        rename_map = dict(zip(selections["source_column"], selections["target_column"]))
        combined = combined.loc[:, columns].rename(columns=rename_map)
    aggregations = _operations(approved, "aggregate")
    combined = _apply_aggregations(combined, aggregations) if not aggregations.empty else combined
    combined = combined.drop_duplicates().reset_index(drop=True)
    combined.insert(0, "record_id", combined.apply(_stable_id, axis=1))
    combined["source_count"] = 1
    output = destination / "retail_summary.parquet"
    combined.to_parquet(output, index=False)
    return [str(output)]
