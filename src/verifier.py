"""VerifierAgent kiểm tra output trước khi ghi file."""

from __future__ import annotations

from src.data_store import DataStore
from src.output_schema import CaseOutput


def _rounded(value: float) -> float:
    result = round(float(value), 2)
    return 0.0 if result == -0.0 else result


class VerifierAgent:
    """Xác minh ID, evidence, số tiền và business invariant."""

    name = "verifier_agent"

    CAUSE_BY_ISSUE = {
        "canceled_order_paid": "ORDER_CANCELED_AFTER_PAYMENT",
        "unavailable_order_paid": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "late_delivery_seller": "SELLER_HANDOFF_AFTER_LIMIT",
        "late_delivery_logistics": "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "valid_split_payment": "MULTIPLE_PAYMENTS_RECONCILED",
        "unsupported_late_claim": "DELIVERY_WITHIN_ESTIMATE",
    }

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def verify(self, result: CaseOutput) -> CaseOutput:
        if len(result.affected_entities.order_ids) != 1:
            raise ValueError("Mỗi case phải có đúng một affected order")

        order_id = result.affected_entities.order_ids[0]
        self.store.get_order(order_id)
        item_rows = self.store.get_order_items(order_id)
        payment_rows = self.store.get_order_payments(order_id)

        valid_item_ids = [
            f"{order_id}:{int(row['order_item_id'])}"
            for _, row in item_rows.iterrows()
        ]
        valid_payment_ids = [
            f"{order_id}:{int(row['payment_sequential'])}"
            for _, row in payment_rows.iterrows()
        ]
        valid_seller_ids = list(dict.fromkeys(item_rows["seller_id"].tolist()))

        affected = result.affected_entities
        if affected.item_ids != valid_item_ids[:5]:
            raise ValueError("affected item IDs không khớp dữ liệu nguồn")
        if affected.payment_ids != valid_payment_ids[:5]:
            raise ValueError("affected payment IDs không khớp dữ liệu nguồn")
        if affected.seller_ids != valid_seller_ids[:3]:
            raise ValueError("affected seller IDs không khớp dữ liệu nguồn")

        related_ids = result.customer_context.related_order_ids
        if order_id in related_ids:
            raise ValueError("Order đang khiếu nại không được nằm trong lịch sử")

        root_causes = result.root_cause_analysis.ranked_causes
        if len(root_causes) != 1 or root_causes[0].rank != 1:
            raise ValueError("Phải có đúng một root cause hạng 1")

        primary_issue = result.case_assessment.primary_issue
        expected_cause = self.CAUSE_BY_ISSUE[primary_issue]
        if root_causes[0].cause_code != expected_cause:
            raise ValueError("Root cause không khớp primary issue")

        responsible_seller_ids = [
            party.party_id
            for party in result.root_cause_analysis.responsible_parties
            if party.party_type == "seller"
        ]
        expected_evidence = (
            [f"order:{order_id}"]
            + [f"item:{item_id}" for item_id in affected.item_ids]
            + [
                f"payment:{payment_id}"
                for payment_id in affected.payment_ids
            ]
            + [
                f"seller:{seller_id}"
                for seller_id in responsible_seller_ids
            ]
            + [f"policy:{expected_cause}"]
        )[:20]
        if result.evidence_ids != expected_evidence:
            raise ValueError("Evidence thiếu, thừa hoặc sai thứ tự")

        item_total = _rounded(item_rows["price"].sum())
        freight_total = _rounded(item_rows["freight_value"].sum())
        payment_total = _rounded(payment_rows["payment_value"].sum())
        payment = result.payment_reconciliation

        if payment.item_total_brl != item_total:
            raise ValueError("item_total_brl không khớp CSV")
        if payment.freight_total_brl != freight_total:
            raise ValueError("freight_total_brl không khớp CSV")
        if payment.payment_total_brl != payment_total:
            raise ValueError("payment_total_brl không khớp CSV")

        if item_rows.empty:
            if (
                payment.expected_total_brl is not None
                or payment.difference_brl is not None
                or payment.reconciled is not None
            ):
                raise ValueError("Null handling sai cho order không có item")
        else:
            expected_total = _rounded(item_total + freight_total)
            difference = _rounded(payment_total - expected_total)
            reconciled = abs(difference) <= 0.10
            if payment.expected_total_brl != expected_total:
                raise ValueError("expected_total_brl không khớp")
            if payment.difference_brl != difference:
                raise ValueError("difference_brl không khớp")
            if payment.reconciled != reconciled:
                raise ValueError("reconciled không khớp")

        if primary_issue in {
            "canceled_order_paid",
            "unavailable_order_paid",
        }:
            expected_refund = payment_total
        elif primary_issue in {
            "late_delivery_seller",
            "late_delivery_logistics",
        }:
            expected_refund = freight_total
        else:
            expected_refund = 0.0

        refund = result.financial_resolution.recommended_refund_brl
        if refund != expected_refund:
            raise ValueError("recommended_refund_brl không đúng policy")

        expected_status = "action_required" if refund > 0 else "no_action"
        if result.case_assessment.case_status != expected_status:
            raise ValueError("case_status không khớp refund")

        return result
