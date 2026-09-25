from __future__ import annotations

from pathlib import Path
import pandas as pd

from agents.sttm_generator import approved_columns, validate_sttm


def create_bronze(paths: list[str], sttm_path: str, output_dir: str | Path) -> list[str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    validate_sttm(sttm_path, paths)
    outputs = []
    for path in paths:
        frame = pd.read_csv(path)
        columns = approved_columns(sttm_path, path)
        if not columns:
            raise ValueError(f"No approved Bronze columns for {path}")
        output = destination / f"{Path(path).stem}.parquet"
        missing = [column for column in columns if column not in frame.columns]
        if missing:
            raise ValueError(f"Approved Bronze columns missing from {path}: {', '.join(missing)}")
        frame.loc[:, columns].to_parquet(output, index=False)
        outputs.append(str(output))
    return outputs
