"""Agent áp dụng EC_POLICY_V2 theo đúng thứ tự ưu tiên."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.agents.customer_agent import CustomerContext
from src.agents.delivery_agent import DeliveryAnalysis
from src.agents.order_product_agent import OrderProductAnalysis
from src.agents.payment_agent import PaymentAnalysis


class ResponsibleParty(BaseModel):
    party_type: str
    party_id: str


class PolicyDecision(BaseModel):
    """Contract PolicyAgent bàn giao cho Coordinator."""

    primary_issue: str
    secondary_issues: list[str]
    case_status: Literal["action_required", "no_action"]
    confidence: float
    cause_code: str
    responsible_parties: list[ResponsibleParty]
    recommended_refund_brl: float
    resolution_actions: list[str]


class PolicyAgent:
    """Áp dụng policy; không tự truy cập CSV hoặc ghi output."""

    name = "policy_agent"

    CAUSE_BY_ISSUE = {
        "canceled_order_paid": "ORDER_CANCELED_AFTER_PAYMENT",
        "unavailable_order_paid": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
        "late_delivery_seller": "SELLER_HANDOFF_AFTER_LIMIT",
        "late_delivery_logistics": "CARRIER_DELIVERED_AFTER_ESTIMATE",
        "valid_split_payment": "MULTIPLE_PAYMENTS_RECONCILED",
        "unsupported_late_claim": "DELIVERY_WITHIN_ESTIMATE",
    }

    def apply(
        self,
        order_analysis: OrderProductAnalysis,
        customer_context: CustomerContext,
        payment_analysis: PaymentAnalysis,
        delivery_analysis: DeliveryAnalysis,
    ) -> PolicyDecision:
        order_status = order_analysis.order.order_status
        payment_total = payment_analysis.payment_total_brl
        delivery_variance = delivery_analysis.delivery_variance_hours
        late_seller_ids = delivery_analysis.late_handoff_seller_ids

        # Thứ tự các nhánh này là một phần của EC_POLICY_V2.
        if order_status == "canceled" and payment_total > 0:
            primary_issue = "canceled_order_paid"
        elif order_status == "unavailable" and payment_total > 0:
            primary_issue = "unavailable_order_paid"
        elif (
            delivery_variance is not None
            and delivery_variance > 0
            and late_seller_ids
        ):
            primary_issue = "late_delivery_seller"
        elif delivery_variance is not None and delivery_variance > 0:
            primary_issue = "late_delivery_logistics"
        elif (
            payment_analysis.payment_row_count >= 2
            and payment_analysis.reconciled is True
        ):
            primary_issue = "valid_split_payment"
        elif (
            delivery_variance is not None
            and delivery_variance <= 0
            and payment_analysis.reconciled is True
        ):
            primary_issue = "unsupported_late_claim"
        else:
            raise ValueError(
                f"Order {order_analysis.order.order_id} "
                "không khớp nhánh nào của EC_POLICY_V2"
            )

        secondary_issues: list[str] = []
        if len(order_analysis.items) >= 2:
            secondary_issues.append("multi_item_order")
        if len(order_analysis.seller_ids) >= 2:
            secondary_issues.append("multi_seller_order")
        if payment_analysis.payment_row_count >= 2:
            secondary_issues.append("split_payment")
        if customer_context.related_order_ids:
            secondary_issues.append("repeat_customer")
        if len(order_analysis.category_names) >= 2:
            secondary_issues.append("multiple_categories")

        responsible_parties: list[ResponsibleParty]
        resolution_actions: list[str]

        if primary_issue == "late_delivery_seller":
            responsible_parties = [
                ResponsibleParty(
                    party_type="seller",
                    party_id=seller_id,
                )
                for seller_id in late_seller_ids[:3]
            ]
            refund = payment_analysis.freight_total_brl
            resolution_actions = [
                "refund_freight",
                "review_seller_handoff",
            ]
        elif primary_issue == "late_delivery_logistics":
            responsible_parties = [
                ResponsibleParty(
                    party_type="logistics_provider",
                    party_id="LOGISTICS_PROVIDER",
                )
            ]
            refund = payment_analysis.freight_total_brl
            resolution_actions = [
                "refund_freight",
                "review_carrier_delay",
            ]
        elif primary_issue in {
            "canceled_order_paid",
            "unavailable_order_paid",
        }:
            responsible_parties = [
                ResponsibleParty(
                    party_type="platform",
                    party_id="OLIST_PLATFORM",
                )
            ]
            refund = payment_total
            resolution_actions = [
                "issue_full_refund",
                "verify_refund_completion",
            ]
        elif primary_issue == "valid_split_payment":
            responsible_parties = []
            refund = 0.0
            resolution_actions = ["explain_valid_split_payment"]
        else:
            responsible_parties = []
            refund = 0.0
            resolution_actions = ["reject_late_refund"]

        if "multi_seller_order" in secondary_issues:
            resolution_actions.append("coordinate_multi_seller_case")
        if (
            "split_payment" in secondary_issues
            and primary_issue != "valid_split_payment"
        ):
            resolution_actions.append("verify_payment_allocation")

        refund = round(float(refund), 2)
        if refund == -0.0:
            refund = 0.0

        return PolicyDecision(
            primary_issue=primary_issue,
            secondary_issues=secondary_issues,
            case_status="action_required" if refund > 0 else "no_action",
            confidence=1.0,
            cause_code=self.CAUSE_BY_ISSUE[primary_issue],
            responsible_parties=responsible_parties[:3],
            recommended_refund_brl=refund,
            resolution_actions=resolution_actions[:5],
        )
