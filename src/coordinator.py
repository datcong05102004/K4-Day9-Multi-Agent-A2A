"""Coordinator gọi các agent và lắp output của một case."""

from __future__ import annotations

from src.agents import (
    CustomerAgent,
    DeliveryAgent,
    OrderProductAgent,
    PaymentAgent,
    PolicyAgent,
)
from src.agents.llm_review_agent import LLMReviewAgent
from src.data_store import DataStore
from src.input_schema import CaseInput
from src.output_schema import (
    AffectedEntities,
    CaseAssessment,
    CaseOutput,
    FinancialResolution,
    PaymentReconciliation,
    ProductContext,
    RankedCause,
    RootCauseAnalysis,
)
from src.trace_logger import TraceLogger


class CoordinatorAgent:
    """Điều phối handoff; không tự thực hiện phép tính domain."""

    name = "coordinator_agent"

    def __init__(
        self,
        store: DataStore,
        trace: TraceLogger | None = None,
    ) -> None:
        self.trace = trace
        self.customer_agent = CustomerAgent(store)
        self.order_product_agent = OrderProductAgent(store)
        self.payment_agent = PaymentAgent(store)
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.llm_review_agent = LLMReviewAgent()

    def process_case(self, case: CaseInput) -> CaseOutput:
        order_id = case.customer_request.claimed_order_id
        scope = case.investigation_scope

        customer_context = self.customer_agent.investigate(
            order_id,
            scope.include_customer_history,
        )
        self._log_handoff(
            case.case_id,
            self.customer_agent.name,
            [f"order:{order_id}"],
            {
                "customer_unique_id": (
                    customer_context.customer_unique_id
                ),
                "related_order_count": len(
                    customer_context.related_order_ids
                ),
            },
        )
        order_analysis = self.order_product_agent.investigate(
            order_id,
            scope.include_product_context,
        )
        self._log_handoff(
            case.case_id,
            self.order_product_agent.name,
            [f"order:{order_id}"],
            {
                "item_count": len(order_analysis.items),
                "seller_count": len(order_analysis.seller_ids),
                "product_count": len(order_analysis.product_ids),
            },
        )
        payment_analysis = self.payment_agent.reconcile(order_analysis)
        self._log_handoff(
            case.case_id,
            self.payment_agent.name,
            [f"order:{order_id}"],
            {
                "payment_row_count": (
                    payment_analysis.payment_row_count
                ),
                "payment_total_brl": (
                    payment_analysis.payment_total_brl
                ),
                "reconciled": payment_analysis.reconciled,
            },
        )
        delivery_analysis = self.delivery_agent.analyze(order_analysis)
        self._log_handoff(
            case.case_id,
            self.delivery_agent.name,
            [f"order:{order_id}"],
            {
                "delivery_variance_hours": (
                    delivery_analysis.delivery_variance_hours
                ),
                "late_handoff_seller_ids": (
                    delivery_analysis.late_handoff_seller_ids
                ),
            },
        )
        policy_decision = self.policy_agent.apply(
            order_analysis,
            customer_context,
            payment_analysis,
            delivery_analysis,
        )
        self._log_handoff(
            case.case_id,
            self.policy_agent.name,
            [
                f"order:{order_id}",
                f"policy:{policy_decision.cause_code}",
            ],
            {
                "primary_issue": policy_decision.primary_issue,
                "case_status": policy_decision.case_status,
                "recommended_refund_brl": (
                    policy_decision.recommended_refund_brl
                ),
            },
        )

        item_ids = order_analysis.item_ids[:5]
        seller_ids = order_analysis.seller_ids[:3]
        payment_ids = payment_analysis.payment_ids[:5]

        responsible_seller_ids = [
            party.party_id
            for party in policy_decision.responsible_parties
            if party.party_type == "seller"
        ]
        evidence_ids = (
            [f"order:{order_id}"]
            + [f"item:{item_id}" for item_id in item_ids]
            + [f"payment:{payment_id}" for payment_id in payment_ids]
            + [
                f"seller:{seller_id}"
                for seller_id in responsible_seller_ids
            ]
            + [f"policy:{policy_decision.cause_code}"]
        )[:20]

        result = CaseOutput(
            case_id=case.case_id,
            case_assessment=CaseAssessment(
                primary_issue=policy_decision.primary_issue,
                secondary_issues=policy_decision.secondary_issues,
                case_status=policy_decision.case_status,
                confidence=policy_decision.confidence,
            ),
            affected_entities=AffectedEntities(
                order_ids=[order_id],
                item_ids=item_ids,
                seller_ids=seller_ids,
                payment_ids=payment_ids,
            ),
            customer_context=customer_context,
            product_context=ProductContext(
                product_ids=order_analysis.product_ids[:5],
                category_names=order_analysis.category_names[:5],
            ),
            delivery_analysis=delivery_analysis,
            payment_reconciliation=PaymentReconciliation(
                currency=payment_analysis.currency,
                item_total_brl=payment_analysis.item_total_brl,
                freight_total_brl=payment_analysis.freight_total_brl,
                expected_total_brl=payment_analysis.expected_total_brl,
                payment_total_brl=payment_analysis.payment_total_brl,
                difference_brl=payment_analysis.difference_brl,
                reconciled=payment_analysis.reconciled,
                payment_types=payment_analysis.payment_types,
            ),
            root_cause_analysis=RootCauseAnalysis(
                ranked_causes=[
                    RankedCause(
                        cause_code=policy_decision.cause_code,
                        rank=1,
                    )
                ],
                responsible_parties=policy_decision.responsible_parties,
            ),
            evidence_ids=evidence_ids,
            financial_resolution=FinancialResolution(
                currency="BRL",
                recommended_refund_brl=(
                    policy_decision.recommended_refund_brl
                ),
            ),
            resolution_actions=policy_decision.resolution_actions,
        )

        llm_review = self.llm_review_agent.review(case, result)
        self._log_handoff(
            case.case_id,
            self.llm_review_agent.name,
            result.evidence_ids,
            {
                "api_called": True,
                "approved": llm_review.approved,
                "flagged_fields": llm_review.flagged_fields,
                "response_id": llm_review.response_id,
                "actual_model": llm_review.actual_model,
            },
        )
        return result

    def _log_handoff(
        self,
        case_id: str,
        agent: str,
        input_refs: list[str],
        output_summary: dict,
    ) -> None:
        if self.trace is None:
            return
        self.trace.handoff(
            case_id=case_id,
            agent=agent,
            recipient=self.name,
            input_refs=input_refs,
            output_summary=output_summary,
        )
