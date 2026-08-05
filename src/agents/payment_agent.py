"""Agent tổng hợp và đối soát payment."""

from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel

from src.agents.order_product_agent import OrderProductAnalysis
from src.data_store import DataStore


def _rounded(value: float) -> float:
    result = round(float(value), 2)
    return 0.0 if result == -0.0 else result


def _stable_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


class PaymentAnalysis(BaseModel):
    """Contract PaymentAgent bàn giao cho PolicyAgent và Coordinator."""

    currency: str
    item_total_brl: float
    freight_total_brl: float
    expected_total_brl: float | None
    payment_total_brl: float
    difference_brl: float | None
    reconciled: bool | None
    payment_types: list[str]
    payment_ids: list[str]
    payment_row_count: int


class PaymentAgent:
    """Phân tích payment; không quyết định issue hoặc refund."""

    name = "payment_agent"

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def reconcile(
        self,
        order_analysis: OrderProductAnalysis,
    ) -> PaymentAnalysis:
        order_id = order_analysis.order.order_id
        payment_rows = self.store.get_order_payments(order_id)

        item_total = _rounded(
            sum(item.price for item in order_analysis.items)
        )
        freight_total = _rounded(
            sum(item.freight_value for item in order_analysis.items)
        )
        payment_total = _rounded(payment_rows["payment_value"].sum())

        if order_analysis.items:
            expected_total = _rounded(item_total + freight_total)
            difference = _rounded(payment_total - expected_total)
            reconciled: bool | None = abs(difference) <= 0.10
        else:
            expected_total = None
            difference = None
            reconciled = None

        payment_ids = [
            f"{order_id}:{int(row['payment_sequential'])}"
            for _, row in payment_rows.iterrows()
        ]
        payment_types = _stable_unique(
            payment_rows["payment_type"].tolist()
        )

        return PaymentAnalysis(
            currency="BRL",
            item_total_brl=item_total,
            freight_total_brl=freight_total,
            expected_total_brl=expected_total,
            payment_total_brl=payment_total,
            difference_brl=difference,
            reconciled=reconciled,
            payment_types=payment_types,
            payment_ids=payment_ids,
            payment_row_count=len(payment_rows),
        )
