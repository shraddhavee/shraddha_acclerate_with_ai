from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SENSITIVE_NAMES = ("api_key", "apikey", "token", "password", "secret")


def _redact(value: Any, field_name: str = "") -> Any:
    if any(name in field_name.lower() for name in _SENSITIVE_NAMES):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {key: _redact(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def audit_event(run_id: str, event: str, details: dict[str, Any] | None = None, root: Path | None = None) -> None:
    root = root or Path("data/traces")
    root.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "event": event,
        "details": _redact(details or {}),
    }
    with (root / f"{run_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")
