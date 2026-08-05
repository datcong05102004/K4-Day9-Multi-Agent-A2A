"""Tạo metadata audit cho lượt chạy mới nhất."""

from __future__ import annotations

import json
import platform
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import MODEL_NAME, MODEL_PROVIDER


def write_metadata(path: Path, processed_cases: int) -> None:
    metadata = {
        "generated_at": datetime.now().astimezone().isoformat(
            timespec="milliseconds"
        ),
        "cohort": "K4",
        "repo_starter": "K4-Day9-Multi-Agent-A2A",
        "model_provider": MODEL_PROVIDER,
        "model_name": MODEL_NAME,
        "parameter_size": "4B",
        "framework": (
            "custom Python multi-agent coordinator "
            "with Pydantic handoffs"
        ),
        "runtime": f"Python {platform.python_version()}",
        "pandas_version": pd.__version__,
        "policy_version": "EC_POLICY_V2",
        "execution_mode": (
            "deterministic domain agents with OpenRouter LLM review per case"
        ),
        "processed_cases": processed_cases,
    }
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
