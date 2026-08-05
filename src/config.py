"""Cấu hình dùng chung của hệ thống."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# Tên model phải nằm trong source code, không đặt trong .env.
MODEL_PROVIDER = "openai"
MODEL_NAME = "gpt-4o-mini"

DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGGING_DIR = PROJECT_ROOT / "logging"


def get_openai_api_key() -> str:
    """Đọc API key từ .env và báo lỗi nếu chưa cấu hình."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Thiếu OPENAI_API_KEY. Hãy điền key vào file .env ở root project."
        )
    return api_key
