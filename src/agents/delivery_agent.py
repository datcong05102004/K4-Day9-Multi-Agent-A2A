"""Agent phân tích delivery và seller handoff."""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from src.agents.order_product_agent import OrderProductAnalysis


def _hours_between(
    later: str | None,
    earlier: str | None,
) -> float | None:
    if later is None or earlier is None:
        return None

    later_time = pd.to_datetime(later, errors="coerce")
    earlier_time = pd.to_datetime(earlier, errors="coerce")
    if pd.isna(later_time) or pd.isna(earlier_time):
        return None

    value = round(
        (later_time - earlier_time).total_seconds() / 3600,
        2,
    )
    return 0.0 if value == -0.0 else value


class SellerHandoffAnalysis(BaseModel):
    seller_id: str
    shipping_limit_at: str | None
    handoff_variance_hours: float | None
    late_handoff: bool


class DeliveryAnalysis(BaseModel):
    """Contract DeliveryAgent bàn giao cho PolicyAgent và Coordinator."""

    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None
    delivery_variance_hours: float | None
    seller_handoff_analysis: list[SellerHandoffAnalysis]
    late_handoff_seller_ids: list[str]


class DeliveryAgent:
    """Tính delivery variance; không quyết định responsibility hoặc refund."""

    name = "delivery_agent"

    def analyze(
        self,
        order_analysis: OrderProductAnalysis,
    ) -> DeliveryAnalysis:
        order = order_analysis.order

        # Không có sự kiện carrier handoff thì không đủ bằng chứng để
        # tạo phân tích đúng/muộn cho từng seller.
        if order.carrier_handoff_at is None:
            return DeliveryAnalysis(
                delivered_at=order.delivered_at,
                estimated_delivery_at=order.estimated_delivery_at,
                carrier_handoff_at=None,
                delivery_variance_hours=_hours_between(
                    order.delivered_at,
                    order.estimated_delivery_at,
                ),
                seller_handoff_analysis=[],
                late_handoff_seller_ids=[],
            )

        seller_results: list[SellerHandoffAnalysis] = []
        late_seller_ids: list[str] = []

        for seller_id in order_analysis.seller_ids:
            shipping_limits = [
                item.shipping_limit_at
                for item in order_analysis.items
                if item.seller_id == seller_id
                and item.shipping_limit_at is not None
            ]
            earliest_limit = min(shipping_limits) if shipping_limits else None
            handoff_variance = _hours_between(
                order.carrier_handoff_at,
                earliest_limit,
            )
            late_handoff = (
                handoff_variance is not None
                and handoff_variance > 0
            )

            seller_results.append(
                SellerHandoffAnalysis(
                    seller_id=seller_id,
                    shipping_limit_at=earliest_limit,
                    handoff_variance_hours=handoff_variance,
                    late_handoff=late_handoff,
                )
            )
            if late_handoff:
                late_seller_ids.append(seller_id)

        return DeliveryAnalysis(
            delivered_at=order.delivered_at,
            estimated_delivery_at=order.estimated_delivery_at,
            carrier_handoff_at=order.carrier_handoff_at,
            delivery_variance_hours=_hours_between(
                order.delivered_at,
                order.estimated_delivery_at,
            ),
            seller_handoff_analysis=seller_results,
            late_handoff_seller_ids=late_seller_ids,
        )
