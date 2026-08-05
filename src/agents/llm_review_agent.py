"""LLM agent kiểm tra tính nhất quán của output dự thảo."""

from __future__ import annotations

import json

from openrouter import OpenRouter
from pydantic import BaseModel, Field

from src.config import MODEL_NAME, get_openrouter_api_key
from src.input_schema import CaseInput
from src.output_schema import CaseOutput


class LLMReview(BaseModel):
    """Kết quả audit do model qua OpenRouter trả về."""

    approved: bool
    summary: str
    flagged_fields: list[str] = Field(max_length=5)
    response_id: str
    actual_model: str


class LLMReviewAgent:
    """Gọi model thật để audit output, không tự thay đổi dữ liệu nguồn."""

    name = "llm_review_agent"

    def __init__(self) -> None:
        self.api_key = get_openrouter_api_key()

    def review(self, case: CaseInput, result: CaseOutput) -> LLMReview:
        print(
            f"[LLM] {case.case_id}: "
            f"calling OpenRouter model {MODEL_NAME}...",
            flush=True,
        )
        with OpenRouter(api_key=self.api_key) as client:
            response = client.chat.send(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the final audit agent for an e-commerce "
                            "dispute. Check whether the candidate output is "
                            "internally consistent with the supplied case. "
                            "Do not invent IDs, events, amounts, or policies. "
                            "Approve unless there is a concrete contradiction. "
                            "Return only JSON with approved (boolean), summary "
                            "(string), and flagged_fields (array of at most "
                            "5 strings)."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "case": case.model_dump(mode="json"),
                                "candidate_output": result.model_dump(
                                    mode="json"
                                ),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=200,
            )

        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(
                f"OpenRouter không trả về text cho {case.case_id}"
            )
        payload = json.loads(content)
        review = LLMReview(
            **payload,
            response_id=response.id or "missing-response-id",
            actual_model=response.model or MODEL_NAME,
        )
        print(
            f"[LLM] {case.case_id}: called=true "
            f"model={review.actual_model} response_id={review.response_id} "
            f"approved={review.approved}",
            flush=True,
        )
        return review
