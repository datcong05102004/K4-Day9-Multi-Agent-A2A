"""Lớp truy cập dữ liệu Olist dùng chung cho các agent."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import DATA_DIR


class DataStore:
    """Đọc CSV một lần và cung cấp các phép tra cứu theo order."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.orders = pd.read_csv(
            data_dir / "olist_orders_dataset.csv",
            dtype=str,
        )
        self.order_items = pd.read_csv(
            data_dir / "olist_order_items_dataset.csv",
            dtype={
                "order_id": str,
                "order_item_id": int,
                "product_id": str,
                "seller_id": str,
                "shipping_limit_date": str,
                "price": float,
                "freight_value": float,
            },
        )
        self.order_payments = pd.read_csv(
            data_dir / "olist_order_payments_dataset.csv",
            dtype={
                "order_id": str,
                "payment_sequential": int,
                "payment_type": str,
                "payment_installments": int,
                "payment_value": float,
            },
        )

    def get_order(self, order_id: str) -> pd.Series:
        """Trả về đúng một order hoặc báo lỗi nếu ID không tồn tại."""
        rows = self.orders[self.orders["order_id"].eq(order_id)]
        if rows.empty:
            raise KeyError(f"Không tìm thấy order: {order_id}")
        if len(rows) > 1:
            raise ValueError(f"Order ID bị trùng trong dữ liệu: {order_id}")
        return rows.iloc[0].copy()

    def get_order_items(self, order_id: str) -> pd.DataFrame:
        """Trả về các item row theo đúng thứ tự dữ liệu nguồn."""
        return self.order_items[
            self.order_items["order_id"].eq(order_id)
        ].copy()

    def get_order_payments(self, order_id: str) -> pd.DataFrame:
        """Trả về các payment row theo đúng thứ tự dữ liệu nguồn."""
        return self.order_payments[
            self.order_payments["order_id"].eq(order_id)
        ].copy()
