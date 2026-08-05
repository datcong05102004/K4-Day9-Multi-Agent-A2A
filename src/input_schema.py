"""Schema và hàm đọc input case."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CustomerRequest(BaseModel):
    language: str
    message: str
    claimed_order_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class InvestigationScope(BaseModel):
    include_customer_history: bool
    include_product_context: bool


class CaseInput(BaseModel):
    case_id: str = Field(pattern=r"^EC_\d{3}$")
    customer_request: CustomerRequest
    investigation_scope: InvestigationScope
    policy_version: Literal["EC_POLICY_V2"]


def load_case(path: Path) -> CaseInput:
    """Đọc và validate một input JSON."""
    raw_json = path.read_text(encoding="utf-8")
    return CaseInput.model_validate_json(raw_json)
