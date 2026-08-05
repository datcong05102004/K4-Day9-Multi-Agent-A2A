"""Ghi audit trace của các agent handoff dưới dạng JSONL."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import MODEL_NAME, MODEL_PROVIDER


class TraceLogger:
    def __init__(self, path: Path, reset: bool = False) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if reset:
            self.path.write_text("", encoding="utf-8")
            self.sequence = 0
        elif self.path.exists():
            with self.path.open(encoding="utf-8") as handle:
                self.sequence = sum(1 for line in handle if line.strip())
        else:
            self.path.touch()
            self.sequence = 0

    def handoff(
        self,
        *,
        case_id: str,
        agent: str,
        recipient: str,
        input_refs: list[str],
        output_summary: dict[str, Any],
    ) -> None:
        """Ghi một handoff không chứa secret."""
        self.sequence += 1
        event = {
            "timestamp": datetime.now().astimezone().isoformat(
                timespec="milliseconds"
            ),
            "sequence": self.sequence,
            "case_id": case_id,
            "event": "agent_handoff",
            "agent": agent,
            "recipient": recipient,
            "model_provider": MODEL_PROVIDER,
            "model_name": MODEL_NAME,
            "execution_mode": (
                "openai_llm_review"
                if agent == "llm_review_agent"
                else "deterministic_data_agent"
            ),
            "input_refs": input_refs,
            "output_summary": output_summary,
        }

        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
