"""Agent xác định customer identity và lịch sử order."""

from __future__ import annotations

from pydantic import BaseModel

from src.data_store import DataStore


class CustomerContext(BaseModel):
    """Contract được CustomerAgent bàn giao cho Coordinator."""

    customer_unique_id: str
    related_order_ids: list[str]


class CustomerAgent:
    """Phân tích domain customer; không xử lý payment hoặc delivery."""

    name = "customer_agent"

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def investigate(
        self,
        order_id: str,
        include_customer_history: bool,
    ) -> CustomerContext:
        order = self.store.get_order(order_id)
        customer = self.store.get_customer(order["customer_id"])
        customer_unique_id = customer["customer_unique_id"]

        related_order_ids: list[str] = []
        if include_customer_history:
            customer_orders = self.store.get_orders_by_customer_unique_id(
                customer_unique_id
            )
            related_order_ids = [
                related_order_id
                for related_order_id in customer_orders["order_id"].tolist()
                if related_order_id != order_id
            ][:5]

        return CustomerContext(
            customer_unique_id=customer_unique_id,
            related_order_ids=related_order_ids,
        )
