from __future__ import annotations

from pathlib import Path
import pandas as pd

from agents.sttm_generator import approved_mappings


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame = frame.drop_duplicates()
    for column in frame.select_dtypes(include="object").columns:
        frame[column] = frame[column].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA})
    return frame.reset_index(drop=True)


def _cast(frame: pd.DataFrame, mappings: pd.DataFrame) -> pd.DataFrame:
    for _, mapping in mappings.iterrows():
        column = mapping["target_column"]
        datatype = mapping["datatype"].lower()
        if column not in frame.columns:
            continue
        if "date" in column.lower() or column.endswith("_at") or "datetime" in datatype:
            frame[column] = pd.to_datetime(frame[column], errors="coerce", utc=True).dt.normalize()
        elif datatype.startswith(("int", "uint")):
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
        elif datatype.startswith(("float", "double", "decimal")):
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Float64")
        elif datatype in {"bool", "boolean"}:
            frame[column] = frame[column].astype("boolean")
        else:
            frame[column] = frame[column].astype("string")
    return frame


def create_silver(bronze_paths: list[str], sttm_path: str, output_dir: str | Path) -> list[str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    outputs = []
    for path in bronze_paths:
        mappings = approved_mappings(sttm_path, path)
        if mappings.empty:
            raise ValueError(f"No approved Silver columns for {path}")
        source_columns = mappings["source_column"].tolist()
        missing = [column for column in source_columns if column not in pd.read_parquet(path).columns]
        if missing:
            raise ValueError(f"Approved Silver columns missing from {path}: {', '.join(missing)}")
        frame = pd.read_parquet(path).loc[:, source_columns].rename(
            columns=dict(zip(source_columns, mappings["target_column"]))
        )
        frame = _clean(frame)
        frame = _cast(frame, mappings)
        output = destination / Path(path).name
        frame.to_parquet(output, index=False)
        outputs.append(str(output))
    return outputs
