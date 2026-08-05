"""LLM agent kiểm tra tính nhất quán của output dự thảo."""

from __future__ import annotations

import json

from openai import OpenAI
from pydantic import BaseModel, Field

from src.config import MODEL_NAME, get_openai_api_key
from src.input_schema import CaseInput
from src.output_schema import CaseOutput


class LLMReview(BaseModel):
    """Kết quả audit do model OpenAI trả về."""

    approved: bool
    summary: str
    flagged_fields: list[str] = Field(max_length=5)
    response_id: str
    actual_model: str


class LLMReviewAgent:
    """Gọi model thật để audit output, không tự thay đổi dữ liệu nguồn."""

    name = "llm_review_agent"

    def __init__(self) -> None:
        self.client = OpenAI(api_key=get_openai_api_key())

    def review(self, case: CaseInput, result: CaseOutput) -> LLMReview:
        print(
            f"[LLM] {case.case_id}: calling OpenAI model {MODEL_NAME}...",
            flush=True,
        )
        response = self.client.responses.create(
            model=MODEL_NAME,
            instructions=(
                "You are the final audit agent for an e-commerce dispute. "
                "Check only whether the candidate output is internally "
                "consistent with the supplied case request. Do not invent "
                "IDs, events, amounts, or policies. Approve unless there is "
                "a concrete contradiction. Return the required JSON."
            ),
            input=json.dumps(
                {
                    "case": case.model_dump(mode="json"),
                    "candidate_output": result.model_dump(mode="json"),
                },
                ensure_ascii=False,
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "case_review",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "approved": {"type": "boolean"},
                            "summary": {"type": "string"},
                            "flagged_fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 5,
                            },
                        },
                        "required": [
                            "approved",
                            "summary",
                            "flagged_fields",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            temperature=0,
            max_output_tokens=200,
            store=False,
        )
        payload = json.loads(response.output_text)
        review = LLMReview(
            **payload,
            response_id=response.id,
            actual_model=response.model,
        )
        print(
            f"[LLM] {case.case_id}: called=true "
            f"model={review.actual_model} response_id={review.response_id} "
            f"approved={review.approved}",
            flush=True,
        )
        return review
