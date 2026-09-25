from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LocalMemory:
    def __init__(self, path: str | Path = "data/memory.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def remember(self, key: str, value: Any) -> None:
        data = self.read()
        data[key] = value
        self.path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
