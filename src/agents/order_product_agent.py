"""Agent phân tích order, item, seller và product context."""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd
from pydantic import BaseModel

from src.data_store import DataStore


def _optional_value(value: Any) -> Any:
    return None if pd.isna(value) else value


def _stable_unique(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[Any] = set()
    for value in values:
        if pd.isna(value) or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


class OrderInfo(BaseModel):
    order_id: str
    order_status: str
    delivered_at: str | None
    estimated_delivery_at: str | None
    carrier_handoff_at: str | None


class OrderItemInfo(BaseModel):
    order_item_id: int
    product_id: str
    seller_id: str
    shipping_limit_at: str | None
    price: float
    freight_value: float


class OrderProductAnalysis(BaseModel):
    """Contract được bàn giao cho PaymentAgent và DeliveryAgent."""

    order: OrderInfo
    items: list[OrderItemInfo]
    item_ids: list[str]
    seller_ids: list[str]
    product_ids: list[str]
    category_names: list[str]


class OrderProductAgent:
    """Phân tích domain order/product; không tính payment hoặc policy."""

    name = "order_product_agent"

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def investigate(
        self,
        order_id: str,
        include_product_context: bool,
    ) -> OrderProductAnalysis:
        order_row = self.store.get_order(order_id)
        item_rows = self.store.get_order_items(order_id)

        items = [
            OrderItemInfo(
                order_item_id=int(row["order_item_id"]),
                product_id=row["product_id"],
                seller_id=row["seller_id"],
                shipping_limit_at=_optional_value(row["shipping_limit_date"]),
                price=float(row["price"]),
                freight_value=float(row["freight_value"]),
            )
            for _, row in item_rows.iterrows()
        ]

        item_ids = [
            f"{order_id}:{item.order_item_id}"
            for item in items
        ]
        seller_ids = _stable_unique(item.seller_id for item in items)

        product_ids: list[str] = []
        category_names: list[str] = []
        if include_product_context:
            product_ids = _stable_unique(item.product_id for item in items)
            categories = [
                self.store.get_product(product_id)["product_category_name"]
                for product_id in product_ids
            ]
            category_names = _stable_unique(categories)

        return OrderProductAnalysis(
            order=OrderInfo(
                order_id=order_id,
                order_status=order_row["order_status"],
                delivered_at=_optional_value(
                    order_row["order_delivered_customer_date"]
                ),
                estimated_delivery_at=_optional_value(
                    order_row["order_estimated_delivery_date"]
                ),
                carrier_handoff_at=_optional_value(
                    order_row["order_delivered_carrier_date"]
                ),
            ),
            items=items,
            item_ids=item_ids,
            seller_ids=seller_ids,
            product_ids=product_ids,
            category_names=category_names,
        )
