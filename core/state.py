from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class PipelineState:
    run_id: str
    uploaded_files: list[str] = field(default_factory=list)
    business_intent: str = ""
    task_description: str = ""
    profile_path: str | None = None
    sttm_bronze_path: str | None = None
    bronze_output_paths: list[str] = field(default_factory=list)
    sttm_silver_path: str | None = None
    silver_output_paths: list[str] = field(default_factory=list)
    sttm_gold_path: str | None = None
    gold_output_paths: list[str] = field(default_factory=list)
    report_path: str | None = None
    status: str = "created"
    errors: list[str] = field(default_factory=list)
    approvals: dict[str, bool] = field(default_factory=dict)
    decisions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "PipelineState":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))
