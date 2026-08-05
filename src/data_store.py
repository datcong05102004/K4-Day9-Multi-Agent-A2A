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
        self.customers = pd.read_csv(
            data_dir / "olist_customers_dataset.csv",
            dtype=str,
        )
        self.products = pd.read_csv(
            data_dir / "olist_products_dataset.csv",
            dtype=str,
        )
        self.sellers = pd.read_csv(
            data_dir / "olist_sellers_dataset.csv",
            dtype=str,
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
        """Trả về payment row theo khóa nghiệp vụ payment_sequential."""
        rows = self.order_payments[
            self.order_payments["order_id"].eq(order_id)
        ].copy()
        return rows.sort_values(
            "payment_sequential",
            kind="stable",
        )

    def get_customer(self, customer_id: str) -> pd.Series:
        """Trả về customer row tương ứng với một order."""
        rows = self.customers[self.customers["customer_id"].eq(customer_id)]
        if rows.empty:
            raise KeyError(f"Không tìm thấy customer: {customer_id}")
        if len(rows) > 1:
            raise ValueError(f"Customer ID bị trùng trong dữ liệu: {customer_id}")
        return rows.iloc[0].copy()

    def get_product(self, product_id: str) -> pd.Series:
        """Trả về product row theo product_id."""
        rows = self.products[self.products["product_id"].eq(product_id)]
        if rows.empty:
            raise KeyError(f"Không tìm thấy product: {product_id}")
        if len(rows) > 1:
            raise ValueError(f"Product ID bị trùng trong dữ liệu: {product_id}")
        return rows.iloc[0].copy()

    def get_seller(self, seller_id: str) -> pd.Series:
        """Trả về seller row theo seller_id."""
        rows = self.sellers[self.sellers["seller_id"].eq(seller_id)]
        if rows.empty:
            raise KeyError(f"Không tìm thấy seller: {seller_id}")
        if len(rows) > 1:
            raise ValueError(f"Seller ID bị trùng trong dữ liệu: {seller_id}")
        return rows.iloc[0].copy()

    def get_orders_by_customer_unique_id(
        self,
        customer_unique_id: str,
    ) -> pd.DataFrame:
        """Tìm các order của cùng khách hàng theo thứ tự bảng orders."""
        customer_ids = self.customers.loc[
            self.customers["customer_unique_id"].eq(customer_unique_id),
            "customer_id",
        ]
        return self.orders[
            self.orders["customer_id"].isin(customer_ids)
        ].copy()
