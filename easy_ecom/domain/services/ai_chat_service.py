from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import secrets
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import (
    AIAgentProfileModel,
    AIChatChannelModel,
    AIConversationModel,
    AIMessageModel,
    AIToolCallModel,
    AuditLogModel,
    ClientModel,
    LocationModel,
    ProductVariantModel,
    SalesOrderModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.commerce_service import (
    CommerceBaseService,
    SalesService,
    as_decimal,
    build_variant_label,
)


DEFAULT_ALLOWED_ACTIONS = {
    "product_qa": True,
    "recommendations": True,
    "cart_building": True,
    "order_confirmation": True,
}

DEFAULT_HANDOFF_MESSAGE = "I am sending this to our team so they can handle it properly."
DEFAULT_OPENING_MESSAGE = "Hi, how can I help you today?"
HANDOFF_KEYWORDS = (
    "refund",
    "return",
    "chargeback",
    "payment dispute",
    "paid but",
    "wrong item",
    "damaged",
    "complaint",
    "angry",
    "manager",
    "human",
    "real person",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _preview(text: str, limit: int = 280) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}..."


def _normalize_origin(value: str) -> str:
    return value.strip().rstrip("/").lower()


class AIChatService(CommerceBaseService):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__(session_factory)
        self._sales = SalesService(session_factory)

    def get_settings(self, user: AuthenticatedUser, *, api_base_url: str) -> dict[str, Any]:
        self._require_settings_access(user)
        with self._session_factory() as session:
            profile, channel = self._get_or_create_profile_and_channel(session, user=user)
            session.commit()
            return self._settings_payload(profile, channel, api_base_url=api_base_url)

    def update_settings(
        self,
        user: AuthenticatedUser,
        *,
        api_base_url: str,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_settings_access(user)
        with self._session_factory() as session:
            profile, channel = self._get_or_create_profile_and_channel(session, user=user)
            profile.is_enabled = bool(payload.get("is_enabled", False))
            profile.display_name = str(payload.get("display_name", "")).strip() or "Website sales assistant"
            profile.n8n_webhook_url = str(payload.get("n8n_webhook_url", "")).strip()
            profile.persona_prompt = str(payload.get("persona_prompt", "")).strip()
            profile.store_policy = str(payload.get("store_policy", "")).strip()
            profile.faq_json = [
                {
                    "question": str(item.get("question", "")).strip(),
                    "answer": str(item.get("answer", "")).strip(),
                }
                for item in payload.get("faq_entries", [])
                if str(item.get("question", "")).strip() or str(item.get("answer", "")).strip()
            ]
            profile.escalation_rules_json = [
                str(item).strip() for item in payload.get("escalation_rules", []) if str(item).strip()
            ]
            profile.allowed_actions_json = dict(DEFAULT_ALLOWED_ACTIONS | dict(payload.get("allowed_actions", {}) or {}))
            profile.default_location_id = self._validated_location_id(
                session,
                user.client_id,
                payload.get("default_location_id"),
            )
            profile.opening_message = str(payload.get("opening_message", "")).strip()
            profile.handoff_message = str(payload.get("handoff_message", "")).strip()

            channel.status = str(payload.get("channel_status", "active")).strip() or "active"
            channel.display_name = profile.display_name
            channel.allowed_origins_json = [
                str(item).strip().rstrip("/")
                for item in payload.get("allowed_origins", [])
                if str(item).strip()
            ]
            channel.default_location_id = profile.default_location_id

            session.add(
                AuditLogModel(
                    audit_log_id=new_uuid(),
                    client_id=user.client_id,
                    actor_user_id=user.user_id,
                    entity_type="ai_agent_profile",
                    entity_id=str(profile.ai_agent_profile_id),
                    action="ai_agent_settings_updated",
                    request_id=request_id,
                    metadata_json={"channel_id": str(channel.ai_chat_channel_id)},
                )
            )
            session.commit()
            return self._settings_payload(profile, channel, api_base_url=api_base_url)

    def handle_public_message(
        self,
        *,
        widget_key: str,
        browser_session_id: str,
        message: str,
        customer: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        origin: str,
        client_ip: str,
        tool_base_url: str,
    ) -> dict[str, Any]:
        inbound_payload = self._record_public_inbound(
            widget_key=widget_key,
            browser_session_id=browser_session_id,
            message=message,
            customer=customer,
            metadata=metadata,
            origin=origin,
            client_ip=client_ip,
        )

        if inbound_payload["handoff_required"]:
            reply_payload = {
                "reply_text": inbound_payload["handoff_message"],
                "handoff_required": True,
                "handoff_reason": inbound_payload["handoff_reason"],
                "order_status": None,
                "ai_metadata": {"guardrail": "keyword_handoff"},
            }
        else:
            reply_payload = self._invoke_n8n(
                webhook_url=inbound_payload["n8n_webhook_url"],
                payload={
                    "client_id": inbound_payload["client_id"],
                    "channel_id": inbound_payload["channel_id"],
                    "conversation_id": inbound_payload["conversation_id"],
                    "message_id": inbound_payload["inbound_message_id"],
                    "text": message,
                    "recent_context": inbound_payload["recent_context"],
                    "tool_base_url": tool_base_url,
                },
                fallback_message=inbound_payload["handoff_message"],
            )

        return self._record_public_outbound(
            client_id=inbound_payload["client_id"],
            channel_id=inbound_payload["channel_id"],
            conversation_id=inbound_payload["conversation_id"],
            inbound_message_id=inbound_payload["inbound_message_id"],
            reply_payload=reply_payload,
        )

    def tool_context(self, *, client_id: str, conversation_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            conversation, channel, profile = self._load_conversation_bundle(session, client_id, conversation_id)
            client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
            response = {
                "client_id": client_id,
                "channel_id": str(channel.ai_chat_channel_id),
                "conversation_id": str(conversation.ai_conversation_id),
                "business": {
                    "business_name": client.business_name,
                    "currency_code": client.currency_code,
                    "currency_symbol": client.currency_symbol,
                    "timezone": client.timezone,
                    "website_url": client.website_url,
                    "phone": client.phone,
                    "email": client.email,
                    "address": client.address,
                },
                "agent": {
                    "display_name": profile.display_name,
                    "persona_prompt": profile.persona_prompt,
                    "store_policy": profile.store_policy,
                    "faq_entries": profile.faq_json or [],
                    "escalation_rules": profile.escalation_rules_json or [],
                    "allowed_actions": self._allowed_actions(profile),
                    "opening_message": profile.opening_message or DEFAULT_OPENING_MESSAGE,
                    "handoff_message": profile.handoff_message or DEFAULT_HANDOFF_MESSAGE,
                },
                "customer": {
                    "name": conversation.customer_name_snapshot,
                    "phone": conversation.customer_phone_snapshot,
                    "email": conversation.customer_email_snapshot,
                    "address": conversation.customer_address_snapshot,
                },
                "recent_messages": self._recent_messages(session, client_id, str(conversation.ai_conversation_id), limit=12),
                "tool_rules": [
                    "Use EasyEcom tool results as the source of truth.",
                    "Never say an item is available unless variant availability says it can be fulfilled.",
                    "Use handoff for refunds, returns, payment disputes, angry customers, ambiguous variants, or unsupported requests.",
                    "Confirm orders only after explicit customer confirmation and a final availability check.",
                ],
            }
            self._record_tool_call(session, client_id, conversation_id, "context", {}, response)
            session.commit()
            return response

    def tool_catalog_search(
        self,
        *,
        client_id: str,
        conversation_id: str,
        query: str,
        location_id: str | None,
        include_out_of_stock: bool,
        limit: int,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            self._load_conversation_bundle(session, client_id, conversation_id)
            location_context = self._location_context(session, client_id, location_id)
            on_hand_map, reserved_map = self._stock_maps(session, client_id, location_context.active_location_id)
            rows = session.execute(self._apply_variant_search(self._base_variant_stmt(client_id), query)).all()
            items: list[dict[str, Any]] = []
            seen: set[str] = set()
            for product, variant, supplier, category in rows:
                if len(items) >= limit:
                    break
                if product.status != "active" or variant.status != "active":
                    continue
                variant_id = str(variant.variant_id)
                if variant_id in seen:
                    continue
                on_hand = on_hand_map.get(variant_id, Decimal("0"))
                reserved = reserved_map.get(variant_id, Decimal("0"))
                available = on_hand - reserved
                if not include_out_of_stock and available <= Decimal("0"):
                    continue
                price = self._effective_variant_price(product, variant)
                items.append(
                    {
                        "variant_id": variant_id,
                        "product_id": str(product.product_id),
                        "product_name": product.name,
                        "label": build_variant_label(product.name, variant.title),
                        "sku": variant.sku,
                        "brand": product.brand,
                        "category": category.name if category else "",
                        "supplier": supplier.name if supplier else "",
                        "description": product.description,
                        "unit_price": price,
                        "min_price": self._effective_variant_min_price(product, variant),
                        "on_hand": on_hand,
                        "reserved": reserved,
                        "available_to_sell": available,
                        "can_sell": available > Decimal("0") and price is not None and price > Decimal("0"),
                    }
                )
                seen.add(variant_id)
            response = {"items": items}
            self._record_tool_call(
                session,
                client_id,
                conversation_id,
                "catalog.search",
                {
                    "query": query,
                    "location_id": location_id,
                    "include_out_of_stock": include_out_of_stock,
                    "limit": limit,
                },
                response,
            )
            session.commit()
            return response

    def tool_variant_availability(
        self,
        *,
        client_id: str,
        conversation_id: str,
        variant_id: str,
        quantity: Decimal,
        location_id: str | None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            self._load_conversation_bundle(session, client_id, conversation_id)
            location_context = self._location_context(session, client_id, location_id)
            row = session.execute(
                self._base_variant_stmt(client_id).where(ProductVariantModel.variant_id == variant_id)
            ).first()
            if row is None:
                raise ApiException(status_code=404, code="VARIANT_NOT_FOUND", message="Variant was not found")
            product, variant, supplier, category = row
            on_hand_map, reserved_map = self._stock_maps(session, client_id, location_context.active_location_id)
            variant_payload = self._variant_payload(
                product,
                variant,
                on_hand_map.get(str(variant.variant_id), Decimal("0")),
                reserved_map.get(str(variant.variant_id), Decimal("0")),
            )
            variant_payload.update(
                {
                    "supplier": supplier.name if supplier else "",
                    "category": category.name if category else "",
                    "location_id": location_context.active_location_id,
                    "location_name": location_context.active_location_name,
                }
            )
            response = {
                "variant": variant_payload,
                "requested_quantity": quantity,
                "can_fulfill": as_decimal(variant_payload["available_to_sell"]) >= as_decimal(quantity)
                and variant_payload["effective_unit_price"] is not None,
            }
            self._record_tool_call(
                session,
                client_id,
                conversation_id,
                "variant.availability",
                {"variant_id": variant_id, "quantity": quantity, "location_id": location_id},
                response,
            )
            session.commit()
            return response

    def tool_conversation_state(
        self,
        *,
        client_id: str,
        conversation_id: str,
        status: str | None,
        latest_intent: str,
        latest_summary: str,
        customer: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            conversation, _channel, _profile = self._load_conversation_bundle(session, client_id, conversation_id)
            if status:
                conversation.status = status
            if latest_intent:
                conversation.latest_intent = latest_intent.strip()[:64]
            if latest_summary:
                conversation.latest_summary = latest_summary.strip()
            if customer:
                self._apply_customer_snapshot(conversation, customer)
            if metadata:
                conversation.metadata_json = dict((conversation.metadata_json or {}) | metadata)
            response = {
                "conversation_id": str(conversation.ai_conversation_id),
                "status": conversation.status,
                "latest_intent": conversation.latest_intent,
                "latest_summary": conversation.latest_summary,
            }
            self._record_tool_call(
                session,
                client_id,
                conversation_id,
                "conversation.state",
                {
                    "status": status,
                    "latest_intent": latest_intent,
                    "latest_summary": latest_summary,
                    "customer": customer,
                    "metadata": metadata,
                },
                response,
            )
            session.commit()
            return response

    def tool_handoff(self, *, client_id: str, conversation_id: str, reason: str, summary: str = "") -> dict[str, Any]:
        with self._session_factory() as session:
            conversation, _channel, _profile = self._load_conversation_bundle(session, client_id, conversation_id)
            conversation.status = "handoff"
            conversation.handoff_reason = reason.strip()
            if summary.strip():
                conversation.latest_summary = summary.strip()
            response = {
                "conversation_id": str(conversation.ai_conversation_id),
                "status": "handoff",
                "handoff_reason": conversation.handoff_reason,
            }
            self._record_tool_call(
                session,
                client_id,
                conversation_id,
                "handoff",
                {"reason": reason, "summary": summary},
                response,
            )
            session.commit()
            return response

    def tool_confirm_order_from_chat(
        self,
        *,
        client_id: str,
        conversation_id: str,
        customer: dict[str, Any],
        lines: list[dict[str, Any]],
        customer_confirmed: bool,
        confirmation_text: str,
        location_id: str | None,
        notes: str,
    ) -> dict[str, Any]:
        if not customer_confirmed or not confirmation_text.strip():
            raise ApiException(
                status_code=400,
                code="CUSTOMER_CONFIRMATION_REQUIRED",
                message="Explicit customer confirmation is required before confirming an AI chat order",
            )
        if not str(customer.get("name", "")).strip():
            raise ApiException(status_code=400, code="CUSTOMER_NAME_REQUIRED", message="Customer name is required")
        if not str(customer.get("phone", "")).strip():
            raise ApiException(status_code=400, code="CUSTOMER_PHONE_REQUIRED", message="Customer phone is required")
        if not str(customer.get("address", "")).strip():
            raise ApiException(status_code=400, code="CUSTOMER_ADDRESS_REQUIRED", message="Customer delivery address is required")

        with self._session_factory() as session:
            conversation, _channel, profile = self._load_conversation_bundle(session, client_id, conversation_id)
            if not self._allowed_actions(profile).get("order_confirmation", True):
                raise ApiException(status_code=403, code="AI_ORDER_CONFIRMATION_DISABLED", message="AI order confirmation is disabled")
            self._apply_customer_snapshot(conversation, customer)
            session.commit()

        internal_user = self._internal_user(client_id)
        try:
            created = self._sales.create_order(
                internal_user,
                location_id=location_id,
                customer_id=None,
                customer_payload=customer,
                payment_status="unpaid",
                shipment_status="pending",
                notes="\n".join(
                    part
                    for part in [
                        notes.strip(),
                        f"AI chat confirmation: {confirmation_text.strip()}",
                    ]
                    if part
                ),
                lines=lines,
                action="confirm",
            )
        except ApiException as exc:
            if getattr(exc, "code", "") in {"INSUFFICIENT_STOCK", "MIN_PRICE_VIOLATION", "PRICE_REQUIRED", "VARIANT_NOT_FOUND"}:
                self.tool_handoff(client_id=client_id, conversation_id=conversation_id, reason=exc.message, summary=notes)
            raise

        order_id = str(created["sales_order_id"])
        with self._session_factory() as session:
            conversation, channel, _profile = self._load_conversation_bundle(session, client_id, conversation_id)
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.sales_order_id == order_id,
                )
            ).scalar_one()
            order.source_type = "ai_chat"
            order.source_channel_id = channel.ai_chat_channel_id
            order.source_conversation_id = conversation.ai_conversation_id
            session.add(
                AuditLogModel(
                    audit_log_id=new_uuid(),
                    client_id=client_id,
                    actor_user_id=None,
                    entity_type="sales_order",
                    entity_id=order_id,
                    action="ai_chat_order_confirmed",
                    request_id=None,
                    metadata_json={
                        "conversation_id": conversation_id,
                        "channel_id": str(channel.ai_chat_channel_id),
                    },
                )
            )
            response = {"order": self._sales.get_order(internal_user, order_id)}
            self._record_tool_call(
                session,
                client_id,
                conversation_id,
                "orders.confirm_from_chat",
                {
                    "customer": customer,
                    "lines": lines,
                    "customer_confirmed": customer_confirmed,
                    "confirmation_text": confirmation_text,
                    "location_id": location_id,
                    "notes": notes,
                },
                response,
            )
            session.commit()
            response["order"] = self._sales.get_order(internal_user, order_id)
            return response

    def _get_or_create_profile_and_channel(
        self,
        session: Session,
        *,
        user: AuthenticatedUser,
    ) -> tuple[AIAgentProfileModel, AIChatChannelModel]:
        profile = session.execute(
            select(AIAgentProfileModel).where(AIAgentProfileModel.client_id == user.client_id)
        ).scalar_one_or_none()
        if profile is None:
            profile = AIAgentProfileModel(
                ai_agent_profile_id=new_uuid(),
                client_id=user.client_id,
                is_enabled=False,
                display_name="Website sales assistant",
                allowed_actions_json=dict(DEFAULT_ALLOWED_ACTIONS),
                opening_message=DEFAULT_OPENING_MESSAGE,
                handoff_message=DEFAULT_HANDOFF_MESSAGE,
            )
            session.add(profile)
            session.flush()

        channel = session.execute(
            select(AIChatChannelModel).where(
                AIChatChannelModel.client_id == user.client_id,
                AIChatChannelModel.channel_type == "website",
            )
        ).scalar_one_or_none()
        if channel is None:
            channel = AIChatChannelModel(
                ai_chat_channel_id=new_uuid(),
                client_id=user.client_id,
                agent_profile_id=profile.ai_agent_profile_id,
                channel_type="website",
                display_name=profile.display_name,
                status="active",
                widget_key=self._new_widget_key(session),
                allowed_origins_json=[],
                default_location_id=profile.default_location_id,
                created_by_user_id=user.user_id,
            )
            session.add(channel)
            session.flush()
        return profile, channel

    def _settings_payload(
        self,
        profile: AIAgentProfileModel,
        channel: AIChatChannelModel,
        *,
        api_base_url: str,
    ) -> dict[str, Any]:
        return {
            "profile_id": str(profile.ai_agent_profile_id),
            "channel_id": str(channel.ai_chat_channel_id),
            "widget_key": channel.widget_key,
            "channel_status": channel.status,
            "is_enabled": bool(profile.is_enabled),
            "display_name": profile.display_name,
            "n8n_webhook_url": profile.n8n_webhook_url,
            "persona_prompt": profile.persona_prompt,
            "store_policy": profile.store_policy,
            "faq_entries": profile.faq_json or [],
            "escalation_rules": profile.escalation_rules_json or [],
            "allowed_origins": channel.allowed_origins_json or [],
            "allowed_actions": self._allowed_actions(profile),
            "default_location_id": str(profile.default_location_id) if profile.default_location_id else None,
            "opening_message": profile.opening_message or DEFAULT_OPENING_MESSAGE,
            "handoff_message": profile.handoff_message or DEFAULT_HANDOFF_MESSAGE,
            "widget_script": self._widget_script(api_base_url=api_base_url, widget_key=channel.widget_key),
        }

    def _record_public_inbound(
        self,
        *,
        widget_key: str,
        browser_session_id: str,
        message: str,
        customer: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        origin: str,
        client_ip: str,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.execute(
                select(AIChatChannelModel, AIAgentProfileModel)
                .join(
                    AIAgentProfileModel,
                    AIAgentProfileModel.ai_agent_profile_id == AIChatChannelModel.agent_profile_id,
                )
                .where(AIChatChannelModel.widget_key == widget_key)
            ).first()
            if row is None:
                raise ApiException(status_code=404, code="AI_WIDGET_NOT_FOUND", message="Chat widget was not found")
            channel, profile = row
            if channel.status != "active" or not profile.is_enabled:
                raise ApiException(status_code=403, code="AI_WIDGET_DISABLED", message="Chat widget is not enabled")
            self._validate_public_origin(origin, channel.allowed_origins_json or [])

            conversation = self._get_or_create_conversation(
                session,
                channel=channel,
                browser_session_id=browser_session_id,
                customer=customer,
                metadata=metadata,
            )
            self._enforce_public_rate_limit(session, conversation)
            handoff_reason = self._keyword_handoff_reason(message)
            now = now_utc()
            inbound = AIMessageModel(
                ai_message_id=new_uuid(),
                client_id=channel.client_id,
                ai_conversation_id=conversation.ai_conversation_id,
                ai_chat_channel_id=channel.ai_chat_channel_id,
                direction="inbound",
                message_text=message.strip(),
                content_summary=_preview(message),
                raw_payload_json={
                    "origin": origin,
                    "client_ip": client_ip,
                    "customer": customer or {},
                    "metadata": metadata or {},
                },
                occurred_at=now,
            )
            session.add(inbound)
            conversation.last_message_preview = _preview(message)
            conversation.last_message_at = now
            if handoff_reason:
                conversation.status = "handoff"
                conversation.handoff_reason = handoff_reason
            channel.last_inbound_at = now
            session.commit()
            recent_context = self._recent_messages(session, str(channel.client_id), str(conversation.ai_conversation_id), limit=12)
            return {
                "client_id": str(channel.client_id),
                "channel_id": str(channel.ai_chat_channel_id),
                "conversation_id": str(conversation.ai_conversation_id),
                "inbound_message_id": str(inbound.ai_message_id),
                "n8n_webhook_url": profile.n8n_webhook_url,
                "recent_context": recent_context,
                "handoff_message": profile.handoff_message or DEFAULT_HANDOFF_MESSAGE,
                "handoff_required": bool(handoff_reason),
                "handoff_reason": handoff_reason,
            }

    def _record_public_outbound(
        self,
        *,
        client_id: str,
        channel_id: str,
        conversation_id: str,
        inbound_message_id: str,
        reply_payload: dict[str, Any],
    ) -> dict[str, Any]:
        reply_text = str(reply_payload.get("reply_text", "")).strip() or DEFAULT_HANDOFF_MESSAGE
        now = now_utc()
        with self._session_factory() as session:
            conversation, channel, _profile = self._load_conversation_bundle(session, client_id, conversation_id)
            if bool(reply_payload.get("handoff_required")):
                conversation.status = "handoff"
                conversation.handoff_reason = str(reply_payload.get("handoff_reason", "")).strip() or conversation.handoff_reason
            outbound = AIMessageModel(
                ai_message_id=new_uuid(),
                client_id=client_id,
                ai_conversation_id=conversation_id,
                ai_chat_channel_id=channel_id,
                direction="outbound",
                message_text=reply_text,
                content_summary=_preview(reply_text),
                raw_payload_json={"inbound_message_id": inbound_message_id},
                ai_metadata_json=reply_payload.get("ai_metadata") or {},
                occurred_at=now,
            )
            session.add(outbound)
            conversation.last_message_preview = _preview(reply_text)
            conversation.last_message_at = now
            channel.last_outbound_at = now
            session.commit()
            return {
                "conversation_id": str(conversation.ai_conversation_id),
                "inbound_message_id": inbound_message_id,
                "outbound_message_id": str(outbound.ai_message_id),
                "reply_text": reply_text,
                "status": conversation.status,
                "handoff_required": conversation.status == "handoff",
                "handoff_reason": conversation.handoff_reason,
                "order_status": reply_payload.get("order_status"),
            }

    def _invoke_n8n(self, *, webhook_url: str, payload: dict[str, Any], fallback_message: str) -> dict[str, Any]:
        if not webhook_url.strip():
            return {
                "reply_text": fallback_message,
                "handoff_required": True,
                "handoff_reason": "AI workflow is not configured",
                "ai_metadata": {"n8n_status": "missing_webhook"},
            }
        try:
            response = httpx.post(
                webhook_url,
                json=payload,
                timeout=settings.n8n_webhook_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            parsed = self._parse_n8n_response(data)
            if not parsed["reply_text"]:
                parsed["reply_text"] = fallback_message
                parsed["handoff_required"] = True
                parsed["handoff_reason"] = "AI workflow returned an empty reply"
            return parsed
        except Exception as exc:
            return {
                "reply_text": fallback_message,
                "handoff_required": True,
                "handoff_reason": "AI workflow failed",
                "ai_metadata": {"n8n_status": "failed", "error": str(exc)[:500]},
            }

    def _parse_n8n_response(self, data: Any) -> dict[str, Any]:
        payload = data
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if isinstance(payload, dict) and isinstance(payload.get("json"), dict):
            payload = payload["json"]
        if not isinstance(payload, dict):
            return {"reply_text": str(payload), "handoff_required": False, "handoff_reason": "", "ai_metadata": {"n8n_response": payload}}
        reply_text = (
            payload.get("reply_text")
            or payload.get("reply")
            or payload.get("message")
            or payload.get("text")
            or payload.get("output")
            or ""
        )
        return {
            "reply_text": str(reply_text).strip(),
            "handoff_required": bool(payload.get("handoff_required") or payload.get("handoff")),
            "handoff_reason": str(payload.get("handoff_reason") or "").strip(),
            "order_status": payload.get("order_status"),
            "ai_metadata": {"n8n_response": _json_safe(payload)},
        }

    def _get_or_create_conversation(
        self,
        session: Session,
        *,
        channel: AIChatChannelModel,
        browser_session_id: str,
        customer: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> AIConversationModel:
        conversation = session.execute(
            select(AIConversationModel).where(
                AIConversationModel.client_id == channel.client_id,
                AIConversationModel.ai_chat_channel_id == channel.ai_chat_channel_id,
                AIConversationModel.browser_session_id == browser_session_id,
            )
        ).scalar_one_or_none()
        if conversation is None:
            conversation = AIConversationModel(
                ai_conversation_id=new_uuid(),
                client_id=channel.client_id,
                ai_chat_channel_id=channel.ai_chat_channel_id,
                browser_session_id=browser_session_id,
                status="open",
                metadata_json=metadata or {},
            )
            session.add(conversation)
            session.flush()
        if customer:
            self._apply_customer_snapshot(conversation, customer)
        if metadata:
            conversation.metadata_json = dict((conversation.metadata_json or {}) | metadata)
        return conversation

    def _load_conversation_bundle(
        self,
        session: Session,
        client_id: str,
        conversation_id: str,
    ) -> tuple[AIConversationModel, AIChatChannelModel, AIAgentProfileModel]:
        row = session.execute(
            select(AIConversationModel, AIChatChannelModel, AIAgentProfileModel)
            .join(
                AIChatChannelModel,
                AIChatChannelModel.ai_chat_channel_id == AIConversationModel.ai_chat_channel_id,
            )
            .join(
                AIAgentProfileModel,
                AIAgentProfileModel.ai_agent_profile_id == AIChatChannelModel.agent_profile_id,
            )
            .where(
                AIConversationModel.client_id == client_id,
                AIChatChannelModel.client_id == client_id,
                AIAgentProfileModel.client_id == client_id,
                AIConversationModel.ai_conversation_id == conversation_id,
            )
        ).first()
        if row is None:
            raise ApiException(status_code=404, code="AI_CONVERSATION_NOT_FOUND", message="AI conversation was not found")
        return row

    def _recent_messages(self, session: Session, client_id: str, conversation_id: str, *, limit: int) -> list[dict[str, Any]]:
        rows = session.execute(
            select(AIMessageModel)
            .where(
                AIMessageModel.client_id == client_id,
                AIMessageModel.ai_conversation_id == conversation_id,
            )
            .order_by(AIMessageModel.occurred_at.desc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "message_id": str(item.ai_message_id),
                "direction": item.direction,
                "text": item.message_text,
                "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
            }
            for item in reversed(rows)
        ]

    def _record_tool_call(
        self,
        session: Session,
        client_id: str,
        conversation_id: str,
        tool_name: str,
        request_json: dict[str, Any],
        response_json: dict[str, Any],
    ) -> None:
        now = now_utc()
        session.add(
            AIToolCallModel(
                ai_tool_call_id=new_uuid(),
                client_id=client_id,
                ai_conversation_id=conversation_id,
                tool_name=tool_name,
                status="succeeded",
                request_json=_json_safe(request_json),
                response_json=_json_safe(response_json),
                started_at=now,
                finished_at=now,
            )
        )

    def _apply_customer_snapshot(self, conversation: AIConversationModel, customer: dict[str, Any]) -> None:
        name = str(customer.get("name", "")).strip()
        phone = str(customer.get("phone", "")).strip()
        email = str(customer.get("email", "")).strip()
        address = str(customer.get("address", "")).strip()
        if name:
            conversation.customer_name_snapshot = name
        if phone:
            conversation.customer_phone_snapshot = phone
        if email:
            conversation.customer_email_snapshot = email
        if address:
            conversation.customer_address_snapshot = address

    def _validated_location_id(self, session: Session, client_id: str, location_id: str | None) -> str | None:
        if not location_id:
            return None
        exists = session.execute(
            select(LocationModel.location_id).where(
                LocationModel.client_id == client_id,
                LocationModel.location_id == location_id,
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ApiException(status_code=404, code="LOCATION_NOT_FOUND", message="Default AI location was not found")
        return str(exists)

    def _validate_public_origin(self, origin: str, allowed_origins: list[str]) -> None:
        normalized_allowed = {_normalize_origin(item) for item in allowed_origins if str(item).strip()}
        if "*" in normalized_allowed:
            return
        normalized_origin = _normalize_origin(origin)
        if not normalized_origin and settings.app_env != "production":
            return
        if not normalized_allowed:
            raise ApiException(status_code=403, code="AI_WIDGET_ORIGIN_NOT_CONFIGURED", message="Chat widget origin is not configured")
        if normalized_origin not in normalized_allowed:
            raise ApiException(status_code=403, code="AI_WIDGET_ORIGIN_DENIED", message="Chat widget origin is not allowed")

    def _enforce_public_rate_limit(self, session: Session, conversation: AIConversationModel) -> None:
        limit = max(settings.ai_public_rate_limit_per_minute, 1)
        window_start = now_utc() - timedelta(minutes=1)
        count = session.execute(
            select(func.count(AIMessageModel.ai_message_id)).where(
                AIMessageModel.client_id == conversation.client_id,
                AIMessageModel.ai_conversation_id == conversation.ai_conversation_id,
                AIMessageModel.direction == "inbound",
                AIMessageModel.occurred_at >= window_start,
            )
        ).scalar_one()
        if int(count) >= limit:
            raise ApiException(status_code=429, code="AI_WIDGET_RATE_LIMITED", message="Too many chat messages. Please wait a moment.")

    def _keyword_handoff_reason(self, message: str) -> str:
        lowered = message.lower()
        for keyword in HANDOFF_KEYWORDS:
            if keyword in lowered:
                return f"Customer message matched handoff keyword: {keyword}"
        return ""

    def _allowed_actions(self, profile: AIAgentProfileModel) -> dict[str, bool]:
        raw = profile.allowed_actions_json or {}
        return {key: bool(raw.get(key, default)) for key, default in DEFAULT_ALLOWED_ACTIONS.items()}

    def _require_settings_access(self, user: AuthenticatedUser) -> None:
        if "Settings" not in user.allowed_pages and "SUPER_ADMIN" not in user.roles:
            raise ApiException(status_code=403, code="ACCESS_DENIED", message="Access denied for Settings")

    def _internal_user(self, client_id: str) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=None,  # type: ignore[arg-type]
            client_id=client_id,
            name="EasyEcom AI Agent",
            email="ai-agent@system.easy-ecom",
            business_name=None,
            roles=["CLIENT_OWNER"],
            allowed_pages=["Sales", "Catalog", "Inventory", "Customers", "Settings"],
            billing_plan_code="internal",
            billing_status="internal",
            billing_access_state="paid_active",
        )

    def _new_widget_key(self, session: Session) -> str:
        while True:
            token = secrets.token_urlsafe(32)
            exists = session.execute(
                select(AIChatChannelModel.ai_chat_channel_id).where(AIChatChannelModel.widget_key == token)
            ).scalar_one_or_none()
            if exists is None:
                return token

    def _widget_script(self, *, api_base_url: str, widget_key: str) -> str:
        base = api_base_url.rstrip("/")
        return (
            '<script src="{base}/ai/chat/widget.js" '
            'data-easy-ecom-widget-key="{widget_key}" async></script>'
        ).format(base=base, widget_key=widget_key)
