from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator

from .audit import audit_event


@contextmanager
def trace_step(run_id: str, name: str) -> Iterator[None]:
    started = perf_counter()
    audit_event(run_id, "step_started", {"step": name})
    try:
        yield
    except Exception as exc:
        audit_event(run_id, "step_failed", {"step": name, "error": str(exc)})
        raise
    else:
        audit_event(run_id, "step_completed", {"step": name, "duration_seconds": round(perf_counter() - started, 4)})
