from __future__ import annotations

import argparse
from pathlib import Path

from agents.orchestrator import approve_bronze, approve_gold, approve_silver, new_state, profile_and_prepare, resume_state
from core.config import settings
from core.state import PipelineState


def _approve_interactively(state: PipelineState) -> PipelineState:
    handlers = {
        "awaiting_bronze_approval": ("Bronze", approve_bronze),
        "awaiting_silver_approval": ("Silver", approve_silver),
        "awaiting_gold_approval": ("Gold", approve_gold),
    }
    while state.status in handlers:
        layer, handler = handlers[state.status]
        answer = input(f"Approve {layer} STTM and continue? [y/N]: ").strip().lower()
        state = handler(state, answer in {"y", "yes"})
        print(f"{state.status}: {state.report_path or state.sttm_gold_path or state.sttm_silver_path or state.sttm_bronze_path}")
        if state.status.endswith("rejected"):
            break
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Retail medallion pipeline")
    parser.add_argument("files", nargs="*", help="Input CSV files")
    parser.add_argument("--intent", default="Understand retail performance", help="Business intent")
    parser.add_argument("--auto-approve", action="store_true", help="Approve each generated STTM for demos")
    parser.add_argument("--resume", help="Run ID to resume from data/traces")
    args = parser.parse_args()
    if args.resume:
        state = resume_state(args.resume)
    else:
        if not args.files:
            parser.error("provide at least one CSV file unless --resume is used")
        state = profile_and_prepare(new_state([str(Path(path)) for path in args.files], args.intent))
    print(f"{state.status}: {state.sttm_bronze_path}")
    if args.auto_approve:
        if state.status == "awaiting_bronze_approval":
            state = approve_bronze(state)
        if state.status == "awaiting_silver_approval":
            state = approve_silver(state)
        if state.status == "awaiting_gold_approval":
            state = approve_gold(state)
        print(f"{state.status}: {state.report_path}")
    else:
        _approve_interactively(state)


if __name__ == "__main__":
    main()
