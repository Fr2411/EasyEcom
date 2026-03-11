from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.services.ai_context_service import AiContextService, InquiryPayload
from easy_ecom.domain.services.integrations_service import IntegrationsService, OutboundPreparePayload
from easy_ecom.data.store.postgres_models import AiReviewDraftModel, ChannelConversationModel, ChannelMessageModel

ALLOWED_REVIEW_STATUSES = {"draft_created", "edited", "approved", "rejected", "sent", "failed"}


@dataclass(frozen=True)
class DraftCreatePayload:
    conversation_id: str
    inbound_message_id: str


@dataclass(frozen=True)
class DraftEditPayload:
    edited_text: str


class AiDraftGenerator:
    """Safe, replaceable generation adapter.

    This is intentionally deterministic and grounded in tenant data while provider
    credentials/config are deferred.
    """

    def __init__(self, ai_context_service: AiContextService):
        self.ai_context_service = ai_context_service

    def generate(self, *, client_id: str, inbound_message: str) -> dict[str, object]:
        inquiry = self.ai_context_service.handle_inbound_inquiry(
            client_id=client_id,
            payload=InquiryPayload(message=inbound_message, customer_ref=None),
        )
        intent = str(inquiry.get("intent", "business_summary"))
        context = inquiry.get("context") if isinstance(inquiry.get("context"), dict) else {}

        if intent == "stock_check":
            items = context.get("items", []) if isinstance(context.get("items"), list) else []
            if items:
                top = items[:3]
                lines = [f"- {row.get('product_name', 'Product')}: {row.get('available_qty', 0)} available" for row in top]
                text = "Thanks for your inquiry. Based on our current inventory records:\n" + "\n".join(lines) + "\nPlease confirm the exact product/variant and quantity you need so we can reserve it."
                confidence = "grounded"
            else:
                text = "Thanks for reaching out. I couldn't find enough inventory context to confirm availability right now. Please share the product name/variant and we'll verify manually."
                confidence = "insufficient_context"
        elif intent == "pricing_lookup":
            items = context.get("items", []) if isinstance(context.get("items"), list) else []
            if items:
                top = items[:3]
                lines = [f"- {row.get('product_name', 'Product')}: {row.get('default_price', 0)}" for row in top]
                text = "Thanks for your message. Current listed prices from our system are:\n" + "\n".join(lines) + "\nIf you share the exact product/variant, we can confirm the final quote."
                confidence = "grounded"
            else:
                text = "Thanks for your message. I don't have enough matched product context to confirm the price. Please share the product name/variant for a precise quote."
                confidence = "insufficient_context"
        elif intent == "order_lookup":
            count = int(context.get("confirmed_sales_count", 0) or 0)
            if count > 0:
                text = "Thanks for checking. I can see recent confirmed order activity in our records. Please share your order number so we can confirm your exact order status."
                confidence = "partial"
            else:
                text = "Thanks for checking in. I couldn't locate enough order context from this message alone. Please provide your order number so we can verify the status."
                confidence = "insufficient_context"
        else:
            text = "Thanks for reaching out. We can help once you share the specific product, variant, quantity, or order number so we can provide an accurate update from our records."
            confidence = "insufficient_context"

        return {
            "draft_text": text,
            "intent": intent,
            "confidence": confidence,
            "grounding": {
                "suggested_endpoint": inquiry.get("suggested_endpoint"),
                "guardrails": inquiry.get("guardrails", {}),
            },
        }


class AiReviewService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        ai_context_service: AiContextService,
        integrations_service: IntegrationsService,
        draft_generator: AiDraftGenerator | None = None,
    ):
        self.session_factory = session_factory
        self.ai_context_service = ai_context_service
        self.integrations_service = integrations_service
        self.draft_generator = draft_generator or AiDraftGenerator(ai_context_service)

    def _latest_draft(self, session: Session, *, client_id: str, conversation_id: str) -> AiReviewDraftModel | None:
        return session.execute(
            select(AiReviewDraftModel)
            .where(
                AiReviewDraftModel.client_id == client_id,
                AiReviewDraftModel.conversation_id == conversation_id,
            )
            .order_by(AiReviewDraftModel.created_at.desc())
        ).scalars().first()

    def list_review_conversations(self, *, client_id: str, limit: int = 50) -> list[dict[str, object]]:
        with self.session_factory() as session:
            conversations = session.execute(
                select(ChannelConversationModel)
                .where(ChannelConversationModel.client_id == client_id)
                .order_by(ChannelConversationModel.last_message_at.desc())
                .limit(max(1, min(limit, 100)))
            ).scalars().all()

            items: list[dict[str, object]] = []
            for conv in conversations:
                inbound = session.execute(
                    select(ChannelMessageModel)
                    .where(
                        ChannelMessageModel.client_id == client_id,
                        ChannelMessageModel.conversation_id == conv.conversation_id,
                        ChannelMessageModel.direction == "inbound",
                    )
                    .order_by(ChannelMessageModel.occurred_at.desc())
                ).scalars().first()
                if inbound is None:
                    continue
                latest = self._latest_draft(session, client_id=client_id, conversation_id=conv.conversation_id)
                status = "new"
                if latest is not None:
                    status = "needs_review" if latest.status in {"draft_created", "edited"} else latest.status
                    if status == "rejected":
                        status = "needs_review"

                items.append(
                    {
                        "conversation_id": conv.conversation_id,
                        "channel_id": conv.channel_id,
                        "external_sender_id": conv.external_sender_id,
                        "customer_id": conv.customer_id or None,
                        "status": status,
                        "last_message_at": conv.last_message_at,
                        "preview_message_id": inbound.message_id,
                        "preview_text": inbound.content_summary or inbound.message_text[:280],
                    }
                )
        return items

    def get_review_conversation(self, *, client_id: str, conversation_id: str) -> dict[str, object] | None:
        detail = self.integrations_service.get_conversation(client_id=client_id, conversation_id=conversation_id)
        if detail is None:
            return None
        with self.session_factory() as session:
            latest = self._latest_draft(session, client_id=client_id, conversation_id=conversation_id)
        detail["latest_draft"] = self._to_dict(latest) if latest else None
        return detail

    def create_draft(self, *, client_id: str, requested_by_user_id: str, payload: DraftCreatePayload) -> dict[str, object]:
        with self.session_factory() as session:
            msg = session.execute(
                select(ChannelMessageModel).where(
                    ChannelMessageModel.client_id == client_id,
                    ChannelMessageModel.conversation_id == payload.conversation_id,
                    ChannelMessageModel.message_id == payload.inbound_message_id,
                    ChannelMessageModel.direction == "inbound",
                )
            ).scalar_one_or_none()
            if msg is None:
                raise ValueError("Inbound message not found")

            generated = self.draft_generator.generate(client_id=client_id, inbound_message=msg.message_text)
            now = now_iso()
            row = AiReviewDraftModel(
                draft_id=f"aid-{hashlib.sha1(f'{client_id}-{payload.inbound_message_id}-{now}'.encode()).hexdigest()[:12]}",
                client_id=client_id,
                conversation_id=payload.conversation_id,
                inbound_message_id=payload.inbound_message_id,
                ai_draft_text=str(generated["draft_text"]),
                edited_text="",
                final_text="",
                status="draft_created",
                intent=str(generated.get("intent", "")),
                confidence=str(generated.get("confidence", "")),
                grounding_json=json.dumps(generated.get("grounding", {})),
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
            session.add(row)
            session.commit()
        return self._to_dict(row)

    def edit_draft(self, *, client_id: str, draft_id: str, payload: DraftEditPayload) -> dict[str, object]:
        text = payload.edited_text.strip()
        if not text:
            raise ValueError("edited_text is required")
        with self.session_factory() as session:
            row = session.execute(select(AiReviewDraftModel).where(AiReviewDraftModel.client_id == client_id, AiReviewDraftModel.draft_id == draft_id)).scalar_one_or_none()
            if row is None:
                raise ValueError("Draft not found")
            if row.status in {"sent", "failed"}:
                raise ValueError("Draft can no longer be edited")
            row.edited_text = text
            row.status = "edited"
            row.updated_at = now_iso()
            session.commit()
        return self._to_dict(row)

    def approve_draft(self, *, client_id: str, draft_id: str, approved_by_user_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = session.execute(select(AiReviewDraftModel).where(AiReviewDraftModel.client_id == client_id, AiReviewDraftModel.draft_id == draft_id)).scalar_one_or_none()
            if row is None:
                raise ValueError("Draft not found")
            if row.status in {"sent", "failed", "rejected"}:
                raise ValueError("Draft cannot be approved in current state")
            row.final_text = row.edited_text.strip() or row.ai_draft_text
            row.status = "approved"
            row.approved_by_user_id = approved_by_user_id
            row.approved_at = now_iso()
            row.updated_at = now_iso()
            session.commit()
        return self._to_dict(row)

    def reject_draft(self, *, client_id: str, draft_id: str, rejected_by_user_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = session.execute(select(AiReviewDraftModel).where(AiReviewDraftModel.client_id == client_id, AiReviewDraftModel.draft_id == draft_id)).scalar_one_or_none()
            if row is None:
                raise ValueError("Draft not found")
            if row.status in {"sent", "failed"}:
                raise ValueError("Draft cannot be rejected in current state")
            row.status = "rejected"
            row.updated_at = now_iso()
            if not row.final_text:
                row.final_text = row.edited_text.strip() or row.ai_draft_text
            session.commit()
        return self._to_dict(row)

    def send_draft(self, *, client_id: str, draft_id: str, sent_by_user_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = session.execute(select(AiReviewDraftModel).where(AiReviewDraftModel.client_id == client_id, AiReviewDraftModel.draft_id == draft_id)).scalar_one_or_none()
            if row is None:
                raise ValueError("Draft not found")
            if row.status != "approved":
                raise ValueError("Draft must be approved before sending")

            conversation = session.execute(select(ChannelConversationModel).where(ChannelConversationModel.client_id == client_id, ChannelConversationModel.conversation_id == row.conversation_id)).scalar_one_or_none()
            if conversation is None:
                raise ValueError("Conversation not found")

        try:
            result = self.integrations_service.prepare_outbound(
                client_id=client_id,
                created_by_user_id=sent_by_user_id,
                payload=OutboundPreparePayload(
                    channel_id=conversation.channel_id,
                    conversation_id=conversation.conversation_id,
                    message_text=row.final_text or row.ai_draft_text,
                    recipient_external_id=conversation.external_sender_id,
                    metadata={"source": "ai_review", "draft_id": draft_id},
                ),
            )
            new_status = "sent"
            failed_reason = ""
        except Exception as exc:
            result = {"error": str(exc)}
            new_status = "failed"
            failed_reason = str(exc)

        with self.session_factory() as session:
            row = session.execute(select(AiReviewDraftModel).where(AiReviewDraftModel.client_id == client_id, AiReviewDraftModel.draft_id == draft_id)).scalar_one_or_none()
            assert row is not None
            row.status = new_status
            row.sent_by_user_id = sent_by_user_id
            row.sent_at = now_iso()
            row.failed_reason = failed_reason
            row.send_result_json = json.dumps(result)
            row.updated_at = now_iso()
            session.commit()
        return self._to_dict(row)

    def list_history(self, *, client_id: str, limit: int = 100) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(AiReviewDraftModel)
                .where(AiReviewDraftModel.client_id == client_id)
                .order_by(AiReviewDraftModel.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).scalars().all()
        return [self._to_dict(row) for row in rows]

    @staticmethod
    def _to_dict(row: AiReviewDraftModel | None) -> dict[str, object]:
        if row is None:
            return {}
        status = row.status if row.status in ALLOWED_REVIEW_STATUSES else "failed"
        return {
            "draft_id": row.draft_id,
            "conversation_id": row.conversation_id,
            "inbound_message_id": row.inbound_message_id,
            "status": status,
            "ai_draft_text": row.ai_draft_text,
            "edited_text": row.edited_text,
            "final_text": row.final_text,
            "intent": row.intent,
            "confidence": row.confidence,
            "grounding": json.loads(row.grounding_json or "{}"),
            "requested_by_user_id": row.requested_by_user_id,
            "approved_by_user_id": row.approved_by_user_id or None,
            "sent_by_user_id": row.sent_by_user_id or None,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "approved_at": row.approved_at or None,
            "sent_at": row.sent_at or None,
            "failed_reason": row.failed_reason or None,
            "send_result": json.loads(row.send_result_json or "{}"),
            "human_modified": bool((row.final_text or row.edited_text) and (row.final_text or row.edited_text) != row.ai_draft_text),
        }
