from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.store.postgres_models import (
    AiReviewDraftModel,
    AutomationDecisionModel,
    ChannelConversationModel,
    ChannelMessageModel,
    TenantAutomationPolicyModel,
)
from easy_ecom.domain.services.ai_review_service import AiReviewService
from easy_ecom.domain.services.integrations_service import IntegrationsService, OutboundPreparePayload

LOW_RISK_CATEGORIES = {
    "product_availability",
    "stock_availability",
    "simple_price_inquiry",
    "business_hours_basic_info",
}


@dataclass(frozen=True)
class AutomationPolicyPatch:
    automation_enabled: bool | None = None
    auto_send_enabled: bool | None = None
    emergency_disabled: bool | None = None
    categories: dict[str, bool] | None = None


class AutomationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        ai_review_service: AiReviewService,
        integrations_service: IntegrationsService,
    ):
        self.session_factory = session_factory
        self.ai_review_service = ai_review_service
        self.integrations_service = integrations_service

    @staticmethod
    def _default_categories() -> dict[str, bool]:
        return {
            "product_availability": True,
            "stock_availability": True,
            "simple_price_inquiry": True,
            "business_hours_basic_info": False,
        }

    def _get_or_create_policy(self, session: Session, *, client_id: str) -> TenantAutomationPolicyModel:
        row = session.execute(select(TenantAutomationPolicyModel).where(TenantAutomationPolicyModel.client_id == client_id)).scalar_one_or_none()
        if row is not None:
            return row
        now = now_iso()
        row = TenantAutomationPolicyModel(
            policy_id=f"autopol-{hashlib.sha1(f'{client_id}-{now}'.encode()).hexdigest()[:12]}",
            client_id=client_id,
            automation_enabled="false",
            auto_send_enabled="false",
            emergency_disabled="false",
            categories_json=json.dumps(self._default_categories()),
            updated_by_user_id="system",
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def _as_bool(raw: str | None, default: bool = False) -> bool:
        compact = (raw or "").strip().lower()
        if compact in {"true", "1", "yes", "y"}:
            return True
        if compact in {"false", "0", "no", "n"}:
            return False
        return default

    def _policy_to_dict(self, row: TenantAutomationPolicyModel) -> dict[str, object]:
        try:
            parsed = json.loads(row.categories_json or "{}")
            categories = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            categories = {}
        with_defaults = self._default_categories()
        for key, enabled in categories.items():
            if key in LOW_RISK_CATEGORIES:
                with_defaults[key] = bool(enabled)
        return {
            "policy_id": row.policy_id,
            "client_id": row.client_id,
            "automation_enabled": self._as_bool(row.automation_enabled),
            "auto_send_enabled": self._as_bool(row.auto_send_enabled),
            "emergency_disabled": self._as_bool(row.emergency_disabled),
            "categories": with_defaults,
            "updated_by_user_id": row.updated_by_user_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def get_policy(self, *, client_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._get_or_create_policy(session, client_id=client_id)
            session.commit()
            return self._policy_to_dict(row)

    def patch_policy(self, *, client_id: str, updated_by_user_id: str, payload: AutomationPolicyPatch) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._get_or_create_policy(session, client_id=client_id)
            policy = self._policy_to_dict(row)

            if payload.automation_enabled is not None:
                row.automation_enabled = "true" if payload.automation_enabled else "false"
            if payload.auto_send_enabled is not None:
                row.auto_send_enabled = "true" if payload.auto_send_enabled else "false"
            if payload.emergency_disabled is not None:
                row.emergency_disabled = "true" if payload.emergency_disabled else "false"

            merged = dict(policy["categories"])
            if payload.categories:
                for key, enabled in payload.categories.items():
                    if key not in LOW_RISK_CATEGORIES:
                        raise ValueError(f"Unsupported automation category: {key}")
                    merged[key] = bool(enabled)
            row.categories_json = json.dumps(merged)
            row.updated_by_user_id = updated_by_user_id
            row.updated_at = now_iso()
            session.commit()
            return self._policy_to_dict(row)

    def enable(self, *, client_id: str, updated_by_user_id: str) -> dict[str, object]:
        return self.patch_policy(
            client_id=client_id,
            updated_by_user_id=updated_by_user_id,
            payload=AutomationPolicyPatch(automation_enabled=True, emergency_disabled=False),
        )

    def disable(self, *, client_id: str, updated_by_user_id: str, emergency: bool = False) -> dict[str, object]:
        return self.patch_policy(
            client_id=client_id,
            updated_by_user_id=updated_by_user_id,
            payload=AutomationPolicyPatch(automation_enabled=False, emergency_disabled=emergency),
        )

    @staticmethod
    def _classify(message: str) -> tuple[str, str, bool]:
        msg = message.strip().lower()
        if any(word in msg for word in ["stock", "available", "availability"]):
            return "stock_availability", "keyword_stock", True
        if "product" in msg and "have" in msg:
            return "product_availability", "keyword_product_have", True
        if any(word in msg for word in ["price", "cost", "rate"]):
            return "simple_price_inquiry", "keyword_price", True
        if any(word in msg for word in ["hour", "open", "close", "timing", "address", "contact"]):
            return "business_hours_basic_info", "keyword_business_info", True
        return "unsupported", "no_low_risk_rule_match", False

    def _latest_inbound_message(self, session: Session, *, client_id: str, conversation_id: str) -> tuple[ChannelConversationModel, ChannelMessageModel]:
        conversation = session.execute(
            select(ChannelConversationModel).where(
                ChannelConversationModel.client_id == client_id,
                ChannelConversationModel.conversation_id == conversation_id,
            )
        ).scalar_one_or_none()
        if conversation is None:
            raise ValueError("Conversation not found")
        inbound = session.execute(
            select(ChannelMessageModel)
            .where(
                ChannelMessageModel.client_id == client_id,
                ChannelMessageModel.conversation_id == conversation_id,
                ChannelMessageModel.direction == "inbound",
            )
            .order_by(ChannelMessageModel.occurred_at.desc())
        ).scalars().first()
        if inbound is None:
            raise ValueError("No inbound message found")
        return conversation, inbound

    def evaluate(self, *, client_id: str, conversation_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            policy = self._policy_to_dict(self._get_or_create_policy(session, client_id=client_id))
            _, inbound = self._latest_inbound_message(session, client_id=client_id, conversation_id=conversation_id)

        category, rule, eligible = self._classify(inbound.message_text or inbound.content_summary)
        reason = "eligible_low_risk" if eligible else "unsupported_or_ambiguous"

        if not policy["automation_enabled"]:
            return {
                "conversation_id": conversation_id,
                "inbound_message_id": inbound.message_id,
                "category": category,
                "classification_rule": rule,
                "automation_eligible": False,
                "recommended_action": "human_review",
                "reason": "automation_disabled",
            }
        if policy["emergency_disabled"]:
            return {
                "conversation_id": conversation_id,
                "inbound_message_id": inbound.message_id,
                "category": category,
                "classification_rule": rule,
                "automation_eligible": False,
                "recommended_action": "human_review",
                "reason": "emergency_disabled",
            }
        if not eligible:
            return {
                "conversation_id": conversation_id,
                "inbound_message_id": inbound.message_id,
                "category": category,
                "classification_rule": rule,
                "automation_eligible": False,
                "recommended_action": "human_review",
                "reason": reason,
            }

        categories = policy["categories"] if isinstance(policy.get("categories"), dict) else {}
        if not categories.get(category, False):
            return {
                "conversation_id": conversation_id,
                "inbound_message_id": inbound.message_id,
                "category": category,
                "classification_rule": rule,
                "automation_eligible": False,
                "recommended_action": "human_review",
                "reason": "category_disabled_by_policy",
            }

        generation = self.ai_review_service.draft_generator.generate(client_id=client_id, inbound_message=inbound.message_text or inbound.content_summary)
        confidence = str(generation.get("confidence", "insufficient_context"))
        action = "auto_send" if policy["auto_send_enabled"] and confidence == "grounded" else "draft_for_review"
        return {
            "conversation_id": conversation_id,
            "inbound_message_id": inbound.message_id,
            "category": category,
            "classification_rule": rule,
            "automation_eligible": True,
            "recommended_action": action,
            "reason": "eligible_low_risk",
            "candidate_reply": str(generation.get("draft_text", "")),
            "intent": str(generation.get("intent", "")),
            "confidence": confidence,
            "grounding": generation.get("grounding", {}),
        }

    def _create_review_draft(self, *, session: Session, client_id: str, conversation_id: str, inbound_message_id: str, intent: str, confidence: str, candidate_reply: str, grounding: dict[str, object], requested_by_user_id: str = "system:automation") -> str:
        now = now_iso()
        draft_id = f"d-{hashlib.sha1(f'{client_id}-{conversation_id}-{inbound_message_id}-{now}'.encode()).hexdigest()[:12]}"
        session.add(
            AiReviewDraftModel(
                draft_id=draft_id,
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=inbound_message_id,
                ai_draft_text=candidate_reply,
                edited_text="",
                final_text="",
                status="draft_created",
                intent=intent,
                confidence=confidence,
                grounding_json=json.dumps(grounding),
                requested_by_user_id=requested_by_user_id,
                approved_by_user_id="",
                sent_by_user_id="",
                created_at=now,
                updated_at=now,
                approved_at="",
                sent_at="",
                failed_reason="",
                send_result_json="{}",
            )
        )
        return draft_id

    def _decision_dict(self, row: AutomationDecisionModel) -> dict[str, object]:
        return {
            "decision_id": row.decision_id,
            "conversation_id": row.conversation_id,
            "inbound_message_id": row.inbound_message_id,
            "policy_id": row.policy_id,
            "category": row.category,
            "classification_rule": row.classification_rule,
            "recommended_action": row.recommended_action,
            "outcome": row.outcome,
            "reason": row.reason,
            "confidence": row.confidence,
            "candidate_reply": row.candidate_reply,
            "audit_context": json.loads(row.audit_context_json or "{}"),
            "run_by_user_id": row.run_by_user_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def run(self, *, client_id: str, conversation_id: str, run_by_user_id: str) -> dict[str, object]:
        evaluation = self.evaluate(client_id=client_id, conversation_id=conversation_id)
        with self.session_factory() as session:
            policy_row = self._get_or_create_policy(session, client_id=client_id)
            decision_id = f"adec-{hashlib.sha1(f'{client_id}-{conversation_id}-{now_iso()}'.encode()).hexdigest()[:12]}"
            decision = AutomationDecisionModel(
                decision_id=decision_id,
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=str(evaluation.get("inbound_message_id", "")),
                policy_id=policy_row.policy_id,
                category=str(evaluation.get("category", "unsupported")),
                classification_rule=str(evaluation.get("classification_rule", "")),
                recommended_action=str(evaluation.get("recommended_action", "human_review")),
                outcome="escalated",
                reason=str(evaluation.get("reason", "")),
                confidence=str(evaluation.get("confidence", "")),
                candidate_reply=str(evaluation.get("candidate_reply", "")),
                audit_context_json=json.dumps({"evaluation": evaluation}),
                run_by_user_id=run_by_user_id,
                created_at=now_iso(),
                updated_at=now_iso(),
            )
            session.add(decision)

            if not evaluation.get("automation_eligible", False):
                decision.outcome = "escalated"
            elif evaluation.get("recommended_action") == "draft_for_review":
                draft_id = self._create_review_draft(
                    session=session,
                    client_id=client_id,
                    conversation_id=conversation_id,
                    inbound_message_id=str(evaluation.get("inbound_message_id", "")),
                    intent=str(evaluation.get("intent", "")),
                    confidence=str(evaluation.get("confidence", "insufficient_context")),
                    candidate_reply=str(evaluation.get("candidate_reply", "")),
                    grounding=evaluation.get("grounding", {}) if isinstance(evaluation.get("grounding"), dict) else {},
                )
                decision.outcome = "drafted"
                decision.audit_context_json = json.dumps({"evaluation": evaluation, "draft_id": draft_id})
            else:
                conversation = session.execute(
                    select(ChannelConversationModel).where(
                        ChannelConversationModel.client_id == client_id,
                        ChannelConversationModel.conversation_id == conversation_id,
                    )
                ).scalar_one_or_none()
                if conversation is None:
                    raise ValueError("Conversation not found")
                try:
                    result = self.integrations_service.prepare_outbound(
                        client_id=client_id,
                        created_by_user_id="system:automation",
                        payload=OutboundPreparePayload(
                            channel_id=conversation.channel_id,
                            conversation_id=conversation.conversation_id,
                            message_text=str(evaluation.get("candidate_reply", "")),
                            recipient_external_id=conversation.external_sender_id,
                            metadata={"source": "phase16_automation", "decision_id": decision_id},
                        ),
                    )
                    decision.outcome = "auto_sent"
                    decision.audit_context_json = json.dumps({"evaluation": evaluation, "dispatch": result})
                except Exception as exc:
                    draft_id = self._create_review_draft(
                        session=session,
                        client_id=client_id,
                        conversation_id=conversation_id,
                        inbound_message_id=str(evaluation.get("inbound_message_id", "")),
                        intent=str(evaluation.get("intent", "")),
                        confidence=str(evaluation.get("confidence", "insufficient_context")),
                        candidate_reply=str(evaluation.get("candidate_reply", "")),
                        grounding=evaluation.get("grounding", {}) if isinstance(evaluation.get("grounding"), dict) else {},
                    )
                    decision.outcome = "failed"
                    decision.reason = f"auto_send_failed:{exc}"
                    decision.audit_context_json = json.dumps({"evaluation": evaluation, "draft_id": draft_id, "error": str(exc)})

            decision.updated_at = now_iso()
            session.commit()
            return self._decision_dict(decision)

    def list_history(self, *, client_id: str, limit: int = 100) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(AutomationDecisionModel)
                .where(AutomationDecisionModel.client_id == client_id)
                .order_by(AutomationDecisionModel.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).scalars().all()
        return [self._decision_dict(row) for row in rows]

    def list_queue(self, *, client_id: str, limit: int = 100) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(AutomationDecisionModel)
                .where(
                    AutomationDecisionModel.client_id == client_id,
                    AutomationDecisionModel.outcome.in_(["escalated", "drafted", "failed"]),
                )
                .order_by(AutomationDecisionModel.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).scalars().all()
        return [self._decision_dict(row) for row in rows]
