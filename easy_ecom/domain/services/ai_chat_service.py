from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import json
import re
import secrets
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
    as_optional_decimal,
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
CATALOG_DISCOVERY_PHRASES = (
    "what do you have",
    "show me what you have",
    "show me your products",
    "show me products",
    "show products",
    "show catalog",
    "browse products",
    "browse catalog",
    "what products",
    "what items",
    "what's available",
    "whats available",
    "available products",
    "available items",
    "catalog",
    "collection",
)
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
    "talk to someone",
    "speak to someone",
)
AI_SEARCH_STOPWORDS = {
    "about",
    "actually",
    "aed",
    "after",
    "ahead",
    "also",
    "and",
    "another",
    "arrival",
    "arrive",
    "available",
    "below",
    "can",
    "could",
    "does",
    "delivery",
    "dh",
    "dhs",
    "dirham",
    "dirhams",
    "else",
    "for",
    "good",
    "have",
    "hello",
    "help",
    "instead",
    "looking",
    "minutes",
    "need",
    "option",
    "options",
    "one",
    "please",
    "price",
    "rather",
    "show",
    "shipping",
    "similar",
    "size",
    "slot",
    "slots",
    "something",
    "still",
    "stock",
    "tell",
    "that",
    "the",
    "this",
    "under",
    "usd",
    "use",
    "want",
    "what",
    "with",
    "you",
}

AI_ALLOWED_INTENTS = {
    "product_qa",
    "recommendation",
    "availability",
    "cart_building",
    "order_confirmation",
    "discount",
    "handoff",
    "other",
}
SHOPPING_COLOR_WORDS = {
    "black",
    "white",
    "blue",
    "red",
    "green",
    "grey",
    "gray",
    "yellow",
    "orange",
    "purple",
    "brown",
    "pink",
    "beige",
    "navy",
}
SHOPPING_USE_CASE_PHRASES = (
    "daily running",
    "gym",
    "walking",
    "office",
    "formal",
    "casual",
    "school",
    "training",
    "workout",
    "treadmill",
)
SHOPPING_RECOMMENDATION_PHRASES = (
    "recommend",
    "suggest",
    "show me",
    "something else",
    "another option",
    "another one",
    "similar",
    "cheaper",
    "more affordable",
    "under ",
    "below ",
    "budget option",
    "budget-friendly",
    "on a budget",
)
SHOPPING_PRODUCT_HINTS = (
    "shoe",
    "shoes",
    "sneaker",
    "sneakers",
    "trainer",
    "trainers",
    "bag",
    "bags",
    "backpack",
    "backpacks",
    "boot",
    "boots",
    "sandal",
    "sandals",
    "loafer",
    "loafers",
    "sock",
    "socks",
    "color",
    "colour",
    "size",
)
SHOPPING_AVAILABILITY_PHRASES = (
    "do you have",
    "is it available",
    "is this available",
    "are these available",
    "in stock",
    "have this",
)
SHOPPING_SIMPLE_DISCOVERY_PHRASES = (
    "need ",
    "looking for",
    "want ",
    "show me",
)
SHOPPING_ORDER_ACTION_PHRASES = (
    "place the order",
    "place order",
    "confirm the order",
    "confirm order",
    "i'll take",
    "i will take",
    "buy this",
    "buy it",
    "checkout",
    "add to cart",
    "reserve it",
)
SHOPPING_PRODUCT_QA_PHRASES = (
    "what material",
    "is it leather",
    "is this good for",
    "are these good for",
    "is this okay for",
    "are these okay for",
)
SHOPPING_NON_PRODUCT_TOPIC_PHRASES = (
    "delivery",
    "shipping",
    "slot",
    "slots",
    "arrive",
    "arrival",
    "minutes",
)
SHOPPING_DISCOUNT_NEGOTIATION_PHRASES = (
    "better price",
    "best price",
    "discount",
    "lower the price",
    "cheapest you can do",
)
SHOPPING_NON_SPECIFIC_PRODUCT_TERMS = {
    "aed",
    "affordable",
    "below",
    "cheaper",
    "dh",
    "dhs",
    "dirham",
    "dirhams",
    "good",
    "item",
    "items",
    "model",
    "option",
    "options",
    "pair",
    "product",
    "products",
    "recommend",
    "recommended",
    "similar",
    "something",
    "still",
    "suggest",
    "suggested",
    "thing",
    "things",
    "under",
    "use",
    "usd",
}
SMALL_TALK_GREETING_PHRASES = {
    "assalamualaikum",
    "good afternoon",
    "good evening",
    "good morning",
    "hello",
    "hello there",
    "hey",
    "hey there",
    "hi",
    "hi there",
    "salam",
}
SMALL_TALK_RESET_PATTERNS = (
    r"\bi\s+(?:didn't|didnt|did not)\s+ask(?:\s+for)?\s+anything\s+yet\b",
    r"\bi\s+(?:have not|haven't|havent)\s+asked(?:\s+for)?\s+anything\s+yet\b",
)
SHOPPING_PRODUCT_HINT_SYNONYMS = {
    "shoe": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "shoes": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "sneaker": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "sneakers": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "trainer": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "trainers": {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers"},
    "backpack": {"backpack", "backpacks", "bag", "bags"},
    "backpacks": {"backpack", "backpacks", "bag", "bags"},
    "bag": {"backpack", "backpacks", "bag", "bags"},
    "bags": {"backpack", "backpacks", "bag", "bags"},
    "boot": {"boot", "boots"},
    "boots": {"boot", "boots"},
    "sandal": {"sandal", "sandals"},
    "sandals": {"sandal", "sandals"},
    "loafer": {"loafer", "loafers"},
    "loafers": {"loafer", "loafers"},
    "sock": {"sock", "socks"},
    "socks": {"sock", "socks"},
}
SHOPPING_SIZE_PATTERN = re.compile(r"\b(?:eu|size)\s*([0-9]{1,2}(?:\.[0-9])?)\b", re.IGNORECASE)
SHOPPING_BUDGET_PATTERN = re.compile(
    r"\b(?:under|below|less than|budget(?:\s+of)?|upto|up to|max(?:imum)?\s+(?:budget|price|spend|of)|(?:my\s+)?max(?:imum)?\s+is)\s*(?:aed|usd|dhs?|dirhams?)?\s*([0-9]+(?:\.[0-9]{1,2})?)\b",
    re.IGNORECASE,
)
SHOPPING_PRICE_PATTERN = re.compile(r"\b(?:aed|usd|dhs?|dirhams?)\s*([0-9]+(?:\.[0-9]{1,2})?)\b", re.IGNORECASE)


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
        self._require_ai_assistant_access(user)
        with self._session_factory() as session:
            profile, channel = self._get_or_create_profile_and_channel(session, user=user)
            session.commit()
            return self._settings_payload(profile, channel, api_base_url=api_base_url)

    def list_conversations(self, user: AuthenticatedUser, *, limit: int) -> dict[str, Any]:
        self._require_ai_assistant_access(user)
        safe_limit = max(1, min(int(limit), 100))
        with self._session_factory() as session:
            rows = session.execute(
                select(AIConversationModel, AIChatChannelModel)
                .join(
                    AIChatChannelModel,
                    AIChatChannelModel.ai_chat_channel_id == AIConversationModel.ai_chat_channel_id,
                )
                .where(
                    AIConversationModel.client_id == user.client_id,
                    AIChatChannelModel.client_id == user.client_id,
                )
                .order_by(
                    func.coalesce(AIConversationModel.last_message_at, AIConversationModel.created_at).desc(),
                    AIConversationModel.created_at.desc(),
                )
                .limit(safe_limit)
            ).all()

            conversation_ids = [conversation.ai_conversation_id for conversation, _channel in rows]
            message_counts: dict[str, int] = {}
            if conversation_ids:
                message_counts = {
                    str(conversation_id): int(count)
                    for conversation_id, count in session.execute(
                        select(
                            AIMessageModel.ai_conversation_id,
                            func.count(AIMessageModel.ai_message_id),
                        )
                        .where(
                            AIMessageModel.client_id == user.client_id,
                            AIMessageModel.ai_conversation_id.in_(conversation_ids),
                        )
                        .group_by(AIMessageModel.ai_conversation_id)
                    ).all()
                }

            return {
                "items": [
                    {
                        "conversation_id": str(conversation.ai_conversation_id),
                        "channel_id": str(channel.ai_chat_channel_id),
                        "channel_type": channel.channel_type,
                        "channel_display_name": channel.display_name,
                        "status": conversation.status,
                        "customer_name": conversation.customer_name_snapshot,
                        "customer_phone": conversation.customer_phone_snapshot,
                        "customer_email": conversation.customer_email_snapshot,
                        "latest_intent": conversation.latest_intent,
                        "latest_summary": conversation.latest_summary,
                        "handoff_reason": conversation.handoff_reason,
                        "last_message_preview": conversation.last_message_preview,
                        "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
                        "message_count": message_counts.get(str(conversation.ai_conversation_id), 0),
                    }
                    for conversation, channel in rows
                ]
            }

    def public_chat_bootstrap(self, *, widget_key: str) -> dict[str, Any]:
        with self._session_factory() as session:
            channel, profile = self._load_public_channel_bundle_by_widget(session, widget_key)
            if channel.status != "active" or not profile.is_enabled:
                raise ApiException(status_code=403, code="AI_WIDGET_DISABLED", message="Chat widget is not enabled")
            return {
                "widget_key": widget_key,
                "assistant_name": profile.display_name.strip() or channel.display_name.strip() or "Store assistant",
                "opening_message": profile.opening_message.strip() or DEFAULT_OPENING_MESSAGE,
            }

    def get_conversation_detail(
        self,
        user: AuthenticatedUser,
        *,
        conversation_id: str,
        message_limit: int,
    ) -> dict[str, Any]:
        self._require_ai_assistant_access(user)
        safe_limit = max(1, min(int(message_limit), 100))
        with self._session_factory() as session:
            conversation, channel, _profile = self._load_conversation_bundle(session, user.client_id, conversation_id)
            messages = self._recent_messages(session, user.client_id, conversation_id, limit=safe_limit)
            return {
                "conversation_id": str(conversation.ai_conversation_id),
                "channel_id": str(channel.ai_chat_channel_id),
                "channel_type": channel.channel_type,
                "channel_display_name": channel.display_name,
                "status": conversation.status,
                "customer_name": conversation.customer_name_snapshot,
                "customer_phone": conversation.customer_phone_snapshot,
                "customer_email": conversation.customer_email_snapshot,
                "customer_address": conversation.customer_address_snapshot,
                "latest_intent": conversation.latest_intent,
                "latest_summary": conversation.latest_summary,
                "handoff_reason": conversation.handoff_reason,
                "last_message_preview": conversation.last_message_preview,
                "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
                "messages": messages,
            }

    def update_conversation_status(
        self,
        user: AuthenticatedUser,
        *,
        conversation_id: str,
        status: str,
        handoff_reason: str,
    ) -> dict[str, Any]:
        self._require_ai_assistant_access(user)
        normalized_status = str(status).strip().lower()
        if normalized_status not in {"open", "handoff", "closed"}:
            raise ApiException(status_code=400, code="AI_CONVERSATION_STATUS_INVALID", message="Conversation status is invalid")
        with self._session_factory() as session:
            conversation, _channel, _profile = self._load_conversation_bundle(session, user.client_id, conversation_id)
            conversation.status = normalized_status
            if normalized_status == "open":
                conversation.handoff_reason = ""
            elif normalized_status == "handoff":
                conversation.handoff_reason = handoff_reason.strip() or conversation.handoff_reason or "Conversation requires a human follow-up"
            session.commit()
        return self.get_conversation_detail(user, conversation_id=conversation_id, message_limit=50)

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
        client_message_id: str | None,
        message: str,
        customer: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        origin: str,
        client_ip: str,
        trusted_origins: set[str] | None = None,
    ) -> dict[str, Any]:
        inbound_payload = self._record_public_inbound(
            widget_key=widget_key,
            browser_session_id=browser_session_id,
            client_message_id=client_message_id,
            message=message,
            customer=customer,
            metadata=metadata,
            origin=origin,
            client_ip=client_ip,
            trusted_origins=trusted_origins,
        )

        if inbound_payload.get("final_response"):
            return dict(inbound_payload["final_response"])

        if inbound_payload["handoff_required"]:
            reply_payload = {
                "reply_text": inbound_payload["handoff_message"],
                "handoff_required": True,
                "handoff_reason": inbound_payload["handoff_reason"],
                "order_status": None,
                "latest_intent": "handoff",
                "latest_summary": _preview(message),
                "ai_metadata": {"ai_runtime": "easy_ecom", "guardrail": "keyword_handoff"},
            }
        else:
            reply_payload = self._invoke_easy_ecom_ai(
                client_id=inbound_payload["client_id"],
                conversation_id=inbound_payload["conversation_id"],
                inbound_message_id=inbound_payload["inbound_message_id"],
                text=message,
                recent_context=inbound_payload["recent_context"],
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
            "ai_runtime": "easy_ecom",
            "model_name": settings.openai_model,
            "model_configured": bool(settings.openai_api_key),
            "channel_status": channel.status,
            "is_enabled": bool(profile.is_enabled),
            "display_name": profile.display_name,
            "persona_prompt": profile.persona_prompt,
            "store_policy": profile.store_policy,
            "faq_entries": profile.faq_json or [],
            "escalation_rules": profile.escalation_rules_json or [],
            "allowed_origins": channel.allowed_origins_json or [],
            "allowed_actions": self._allowed_actions(profile),
            "default_location_id": str(profile.default_location_id) if profile.default_location_id else None,
            "opening_message": profile.opening_message or DEFAULT_OPENING_MESSAGE,
            "handoff_message": profile.handoff_message or DEFAULT_HANDOFF_MESSAGE,
            "chat_link": self._chat_link(api_base_url=api_base_url, widget_key=channel.widget_key),
            "widget_script": self._widget_script(api_base_url=api_base_url, widget_key=channel.widget_key),
        }

    def _record_public_inbound(
        self,
        *,
        widget_key: str,
        browser_session_id: str,
        client_message_id: str | None,
        message: str,
        customer: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        origin: str,
        client_ip: str,
        trusted_origins: set[str] | None,
    ) -> dict[str, Any]:
        normalized_client_message_id = str(client_message_id or "").strip() or None
        with self._session_factory() as session:
            channel, profile = self._load_public_channel_bundle_by_widget(session, widget_key)
            if channel.status != "active" or not profile.is_enabled:
                raise ApiException(status_code=403, code="AI_WIDGET_DISABLED", message="Chat widget is not enabled")
            self._validate_public_origin(origin, channel.allowed_origins_json or [], trusted_origins=trusted_origins)

            conversation = self._get_or_create_conversation(
                session,
                channel=channel,
                browser_session_id=browser_session_id,
                customer=customer,
                metadata=metadata,
            )
            if normalized_client_message_id:
                duplicate_payload = self._duplicate_public_message_response(
                    session,
                    client_id=str(channel.client_id),
                    conversation_id=str(conversation.ai_conversation_id),
                    client_message_id=normalized_client_message_id,
                )
                if duplicate_payload is not None:
                    session.commit()
                    return {"final_response": duplicate_payload}
            self._enforce_public_rate_limit(session, conversation)
            existing_handoff_reason = str(conversation.handoff_reason or "").strip()
            small_talk_intent = self._small_talk_intent(message)
            reset_remainder = self._small_talk_reset_remainder(message) if small_talk_intent == "reset" else ""
            reset_requests_human = bool(reset_remainder and self._keyword_handoff_reason(reset_remainder))
            reset_has_shopping_signal = bool(reset_remainder and self._has_specific_shopping_signal(reset_remainder))
            can_recover_with_small_talk = bool(
                small_talk_intent == "greeting"
                or (
                    small_talk_intent == "reset"
                    and not reset_requests_human
                    and (not reset_remainder or reset_has_shopping_signal)
                )
            )
            recoverable_technical_handoff = bool(
                conversation.status == "handoff"
                and existing_handoff_reason
                and can_recover_with_small_talk
                and self._is_recoverable_technical_handoff_reason(existing_handoff_reason)
            )
            if recoverable_technical_handoff:
                conversation.status = "open"
                conversation.handoff_reason = ""
                handoff_reason = ""
            elif conversation.status == "closed":
                handoff_reason = existing_handoff_reason or "Conversation is closed and waiting for a human follow-up"
            elif conversation.status == "handoff":
                handoff_reason = existing_handoff_reason or "Conversation requires a human follow-up"
            else:
                handoff_reason = self._keyword_handoff_reason(message)
            now = now_utc()
            inbound = AIMessageModel(
                ai_message_id=new_uuid(),
                client_id=channel.client_id,
                ai_conversation_id=conversation.ai_conversation_id,
                ai_chat_channel_id=channel.ai_chat_channel_id,
                direction="inbound",
                client_message_id=normalized_client_message_id,
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
            if handoff_reason and conversation.status != "closed":
                conversation.status = "handoff"
                conversation.handoff_reason = handoff_reason
            elif handoff_reason:
                conversation.handoff_reason = handoff_reason
            channel.last_inbound_at = now
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                if normalized_client_message_id:
                    duplicate_payload = self._duplicate_public_message_response(
                        session,
                        client_id=str(channel.client_id),
                        conversation_id=str(conversation.ai_conversation_id),
                        client_message_id=normalized_client_message_id,
                    )
                    if duplicate_payload is not None:
                        return {"final_response": duplicate_payload}
                raise
            recent_context = self._recent_messages(session, str(channel.client_id), str(conversation.ai_conversation_id), limit=12)
            return {
                "client_id": str(channel.client_id),
                "channel_id": str(channel.ai_chat_channel_id),
                "conversation_id": str(conversation.ai_conversation_id),
                "inbound_message_id": str(inbound.ai_message_id),
                "recent_context": recent_context,
                "handoff_message": profile.handoff_message or DEFAULT_HANDOFF_MESSAGE,
                "handoff_required": bool(handoff_reason),
                "handoff_reason": handoff_reason,
            }

    def _load_public_channel_bundle_by_widget(
        self,
        session: Session,
        widget_key: str,
    ) -> tuple[AIChatChannelModel, AIAgentProfileModel]:
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
        return row

    def _duplicate_public_message_response(
        self,
        session: Session,
        *,
        client_id: str,
        conversation_id: str,
        client_message_id: str,
    ) -> dict[str, Any] | None:
        existing_inbound = session.execute(
            select(AIMessageModel).where(
                AIMessageModel.client_id == client_id,
                AIMessageModel.ai_conversation_id == conversation_id,
                AIMessageModel.direction == "inbound",
                AIMessageModel.client_message_id == client_message_id,
            )
        ).scalar_one_or_none()
        if existing_inbound is None:
            return None
        outbound = session.execute(
            select(AIMessageModel)
            .where(
                AIMessageModel.client_id == client_id,
                AIMessageModel.ai_conversation_id == conversation_id,
                AIMessageModel.direction == "outbound",
                AIMessageModel.responded_to_ai_message_id == existing_inbound.ai_message_id,
            )
            .order_by(AIMessageModel.occurred_at.desc(), AIMessageModel.created_at.desc())
        ).scalars().first()
        if outbound is None:
            return {
                "conversation_id": str(conversation_id),
                "inbound_message_id": str(existing_inbound.ai_message_id),
                "outbound_message_id": None,
                "reply_text": "We are still processing your last message. Please wait a moment.",
                "status": "open",
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "was_duplicate": True,
            }
        conversation = session.execute(
            select(AIConversationModel).where(
                AIConversationModel.client_id == client_id,
                AIConversationModel.ai_conversation_id == conversation_id,
            )
        ).scalar_one()
        return self._public_response_payload(
            conversation=conversation,
            inbound_message_id=str(existing_inbound.ai_message_id),
            outbound=outbound,
            was_duplicate=True,
        )

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
            if bool(reply_payload.get("handoff_required")) and conversation.status != "closed":
                conversation.status = "handoff"
                conversation.handoff_reason = str(reply_payload.get("handoff_reason", "")).strip() or conversation.handoff_reason
            latest_intent = str(reply_payload.get("latest_intent", "")).strip()[:64]
            latest_summary = str(reply_payload.get("latest_summary", "")).strip()
            if latest_intent:
                conversation.latest_intent = latest_intent
            if latest_summary:
                conversation.latest_summary = latest_summary
            outbound = AIMessageModel(
                ai_message_id=new_uuid(),
                client_id=client_id,
                ai_conversation_id=conversation_id,
                ai_chat_channel_id=channel_id,
                responded_to_ai_message_id=inbound_message_id,
                direction="outbound",
                message_text=reply_text,
                content_summary=_preview(reply_text),
                raw_payload_json={
                    "inbound_message_id": inbound_message_id,
                    "order_status": reply_payload.get("order_status"),
                },
                ai_metadata_json=reply_payload.get("ai_metadata") or {},
                model_name=str(reply_payload.get("model_name", ""))[:64],
                occurred_at=now,
            )
            session.add(outbound)
            conversation.last_message_preview = _preview(reply_text)
            conversation.last_message_at = now
            channel.last_outbound_at = now
            session.commit()
            return self._public_response_payload(
                conversation=conversation,
                inbound_message_id=inbound_message_id,
                outbound=outbound,
                was_duplicate=False,
            )

    def _public_response_payload(
        self,
        *,
        conversation: AIConversationModel,
        inbound_message_id: str,
        outbound: AIMessageModel,
        was_duplicate: bool,
    ) -> dict[str, Any]:
        raw_payload = outbound.raw_payload_json or {}
        return {
            "conversation_id": str(conversation.ai_conversation_id),
            "inbound_message_id": inbound_message_id,
            "outbound_message_id": str(outbound.ai_message_id),
            "reply_text": outbound.message_text,
            "status": conversation.status,
            "handoff_required": conversation.status in {"handoff", "closed"},
            "handoff_reason": conversation.handoff_reason,
            "order_status": raw_payload.get("order_status"),
            "was_duplicate": was_duplicate,
        }

    def _invoke_easy_ecom_ai(
        self,
        *,
        client_id: str,
        conversation_id: str,
        inbound_message_id: str,
        text: str,
        recent_context: list[dict[str, Any]],
        fallback_message: str,
    ) -> dict[str, Any]:
        model_name = settings.openai_model

        try:
            context_payload = self._build_ai_context(
                client_id=client_id,
                conversation_id=conversation_id,
                text=text,
                recent_context=recent_context,
            )
        except Exception as exc:
            payload = self._ai_handoff_payload(
                fallback_message=fallback_message,
                handoff_reason="AI context preparation failed",
                latest_summary=_preview(text),
                metadata={"model_status": "context_failed", "error": str(exc)[:500]},
            )
            payload["model_name"] = model_name
            self._audit_ai_model_step(
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=inbound_message_id,
                request_json={"model": model_name, "message_preview": _preview(text)},
                response_json=payload,
                status="failed",
                error_message=str(exc)[:1000],
            )
            return payload

        model_request = {
            "model": model_name,
            "message_preview": _preview(text),
            "catalog_item_count": len(context_payload.get("catalog", {}).get("items", [])),
        }

        deterministic_reply = self._deterministic_catalog_reply(context_payload)
        if deterministic_reply is not None:
            deterministic_reply["model_name"] = model_name
            deterministic_reply["ai_metadata"] = dict(
                {
                    "ai_runtime": "easy_ecom",
                    "model": model_name,
                    "model_status": "deterministic_catalog",
                }
                | (deterministic_reply.get("ai_metadata") or {})
            )
            self._audit_ai_model_step(
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=inbound_message_id,
                request_json=dict(model_request | {"strategy": "deterministic_catalog"}),
                response_json=deterministic_reply,
            )
            return deterministic_reply

        small_talk_reply = self._deterministic_small_talk_reply(context_payload)
        if small_talk_reply is not None:
            small_talk_reply["model_name"] = model_name
            small_talk_reply["ai_metadata"] = dict(
                {
                    "ai_runtime": "easy_ecom",
                    "model": model_name,
                    "model_status": "deterministic_small_talk",
                }
                | (small_talk_reply.get("ai_metadata") or {})
            )
            self._audit_ai_model_step(
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=inbound_message_id,
                request_json=dict(model_request | {"strategy": "deterministic_small_talk"}),
                response_json=small_talk_reply,
            )
            return small_talk_reply

        if not settings.openai_api_key:
            payload = self._ai_handoff_payload(
                fallback_message=fallback_message,
                handoff_reason="AI model API key is not configured",
                latest_summary=_preview(text),
                metadata={"model_status": "missing_api_key"},
            )
            payload["model_name"] = model_name
            self._audit_ai_model_step(
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=inbound_message_id,
                request_json=model_request,
                response_json=payload,
                status="failed",
                error_message="AI model API key is not configured",
            )
            return payload

        model_messages = self._build_ai_model_messages(context_payload)
        try:
            model_text, model_response = self._call_ai_model(model_messages)
            parsed = self._parse_ai_model_response(model_text)
            normalized = self._normalize_ai_reply(parsed, fallback_message=fallback_message, text=text)
            normalized = self._maybe_execute_ai_action(
                client_id=client_id,
                conversation_id=conversation_id,
                context_payload=context_payload,
                reply_payload=normalized,
                fallback_message=fallback_message,
            )
            normalized["model_name"] = model_name
            normalized["ai_metadata"] = dict(
                {
                    "ai_runtime": "easy_ecom",
                    "model": model_name,
                    "model_response_id": model_response.get("id", ""),
                }
                | (normalized.get("ai_metadata") or {})
            )
            self._audit_ai_model_step(
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=inbound_message_id,
                request_json=model_request,
                response_json=normalized,
            )
            return normalized
        except Exception as exc:
            fallback_reply = self._deterministic_catalog_reply(context_payload)
            if fallback_reply is not None:
                fallback_reply["model_name"] = model_name
                fallback_reply["ai_metadata"] = dict(
                    {
                        "ai_runtime": "easy_ecom",
                        "model": model_name,
                        "model_status": "request_failed_recovered_with_deterministic_catalog",
                        "error": str(exc)[:500],
                    }
                    | (fallback_reply.get("ai_metadata") or {})
                )
                self._audit_ai_model_step(
                    client_id=client_id,
                    conversation_id=conversation_id,
                    inbound_message_id=inbound_message_id,
                    request_json=dict(model_request | {"strategy": "deterministic_catalog_recovery"}),
                    response_json=fallback_reply,
                    status="degraded",
                    error_message=str(exc)[:1000],
                )
                return fallback_reply
            payload = self._ai_handoff_payload(
                fallback_message=fallback_message,
                handoff_reason="AI model request failed",
                latest_summary=_preview(text),
                metadata={"model_status": "request_failed", "error": str(exc)[:500]},
            )
            payload["model_name"] = model_name
            self._audit_ai_model_step(
                client_id=client_id,
                conversation_id=conversation_id,
                inbound_message_id=inbound_message_id,
                request_json=model_request,
                response_json=payload,
                status="failed",
                error_message=str(exc)[:1000],
            )
            return payload

    def _build_ai_context(
        self,
        *,
        client_id: str,
        conversation_id: str,
        text: str,
        recent_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            conversation, channel, profile = self._load_conversation_bundle(session, client_id, conversation_id)
            client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
            location_id = str(profile.default_location_id or channel.default_location_id or "") or None
            location_context = self._location_context(session, client_id, location_id)
            metadata = conversation.metadata_json if isinstance(conversation.metadata_json, dict) else {}
            existing_preferences = metadata.get("shopping_preferences") if isinstance(metadata.get("shopping_preferences"), dict) else {}
            shopping_preferences = self._extract_shopping_preferences(
                text=text,
                recent_context=recent_context,
                existing_preferences=existing_preferences,
            )
            conversation.metadata_json = dict(metadata | {"shopping_preferences": shopping_preferences})
            catalog_items = self._catalog_items_for_ai(
                session,
                client_id,
                text,
                location_context.active_location_id,
                preferences=shopping_preferences,
            )
            payload = {
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
                "conversation": {
                    "conversation_id": str(conversation.ai_conversation_id),
                    "status": conversation.status,
                    "latest_intent": conversation.latest_intent,
                    "latest_summary": conversation.latest_summary,
                    "recent_messages": recent_context,
                    "shopping_preferences": shopping_preferences,
                },
                "stock_location": {
                    "location_id": location_context.active_location_id,
                    "location_name": location_context.active_location_name,
                },
                "catalog": {
                    "items": catalog_items,
                    "source": "EasyEcom ledger-derived variant availability at the active stock location",
                },
                "current_customer_message": text.strip(),
                "guardrails": [
                    "Use only the facts in this payload. Do not invent products, stock, prices, policies, delivery promises, refunds, or payment outcomes.",
                    "Availability is variant-level and equals available_to_sell. Never say an item is available unless can_sell is true.",
                    "Use the tenant policy and FAQ as approved policy. If a request falls outside policy, hand off.",
                    "Do not offer or accept a unit price below min_price. Hand off discount requests that violate min_price.",
                    "For refunds, returns, payment disputes, angry customers, human requests, unsupported requests, or uncertain action validation, hand off.",
                    "For order confirmation, require explicit customer confirmation plus customer name, phone, and delivery address. The backend will re-check stock before creating any order.",
                    "For normal shopping questions, prefer one direct answer or one clarifying question before human handoff.",
                    "Never fulfill, refund, cancel, or record payment automatically.",
                ],
            }
            self._record_tool_call(
                session,
                client_id,
                conversation_id,
                "easy_ecom.ai.context",
                {"message_preview": _preview(text), "location_id": location_context.active_location_id},
                {
                    "catalog_item_count": len(catalog_items),
                    "location_id": location_context.active_location_id,
                    "recent_message_count": len(recent_context),
                    "shopping_preferences": shopping_preferences,
                },
            )
            session.commit()
            return payload

    def _catalog_items_for_ai(
        self,
        session: Session,
        client_id: str,
        text: str,
        location_id: str,
        *,
        limit: int = 8,
        preferences: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        on_hand_map, reserved_map = self._stock_maps(session, client_id, location_id)
        candidates: list[tuple[Any, Any, Any, Any]] = []
        seen_variants: set[str] = set()

        def add_rows(rows: list[tuple[Any, Any, Any, Any]]) -> None:
            for row in rows:
                _product, variant, _supplier, _category = row
                variant_id = str(variant.variant_id)
                if variant_id in seen_variants:
                    continue
                seen_variants.add(variant_id)
                candidates.append(row)

        search_terms = self._catalog_search_terms(text=text, preferences=preferences)
        for term in search_terms:
            if len(candidates) >= limit * 3:
                break
            if not term.strip():
                continue
            rows = session.execute(self._apply_variant_search(self._base_variant_stmt(client_id), term).limit(limit * 2)).all()
            add_rows(rows)

        if not candidates and self._wants_catalog_discovery(text):
            rows = session.execute(self._base_variant_stmt(client_id).limit(limit * 3)).all()
            add_rows(rows)

        items: list[dict[str, Any]] = []
        for product, variant, supplier, category in candidates:
            if product.status != "active" or variant.status != "active":
                continue
            variant_id = str(variant.variant_id)
            on_hand = on_hand_map.get(variant_id, Decimal("0"))
            reserved = reserved_map.get(variant_id, Decimal("0"))
            available = on_hand - reserved
            price = self._effective_variant_price(product, variant)
            min_price = self._effective_variant_min_price(product, variant)
            items.append(
                {
                    "variant_id": variant_id,
                    "product_id": str(product.product_id),
                    "product_name": product.name,
                    "variant_title": variant.title,
                    "label": build_variant_label(product.name, variant.title),
                    "sku": variant.sku,
                    "brand": product.brand,
                    "category": category.name if category else "",
                    "supplier": supplier.name if supplier else "",
                    "description": _preview(product.description or "", limit=320),
                    "unit_price": price,
                    "min_price": min_price,
                    "on_hand": on_hand,
                    "reserved": reserved,
                    "available_to_sell": available,
                    "can_sell": available > Decimal("0") and price is not None and price > Decimal("0"),
                }
            )
        return self._rank_catalog_items_for_preferences(items, preferences, limit=limit)

    def _ai_search_terms(self, text: str) -> list[str]:
        normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
        terms: list[str] = []
        seen: set[str] = set()
        for token in normalized.split():
            if token.isdigit() or len(token) < 3 or token in AI_SEARCH_STOPWORDS or token in seen:
                continue
            seen.add(token)
            terms.append(token)
            if len(terms) >= 8:
                break
        return terms

    def _wants_catalog_discovery(self, text: str) -> bool:
        lowered = " ".join(text.lower().split())
        return any(phrase in lowered for phrase in CATALOG_DISCOVERY_PHRASES)

    def _extract_shopping_preferences(
        self,
        *,
        text: str,
        recent_context: list[dict[str, Any]],
        existing_preferences: dict[str, Any],
    ) -> dict[str, Any]:
        base = existing_preferences if isinstance(existing_preferences, dict) else {}
        preferences = {
            "product_terms": [str(item).strip().lower() for item in base.get("product_terms", []) if str(item).strip()],
            "colors": [str(item).strip().lower() for item in base.get("colors", []) if str(item).strip()],
            "sizes": [str(item).strip() for item in base.get("sizes", []) if str(item).strip()],
            "use_case_terms": [str(item).strip().lower() for item in base.get("use_case_terms", []) if str(item).strip()],
            "max_budget": str(base.get("max_budget") or "").strip(),
            "last_referenced_price": str(base.get("last_referenced_price") or "").strip(),
            "price_preference": str(base.get("price_preference") or "any").strip() or "any",
            "wants_recommendation": bool(base.get("wants_recommendation")),
            "wants_availability": bool(base.get("wants_availability")),
        }

        customer_turns = [
            str(item.get("text") or "").strip()
            for item in recent_context
            if str(item.get("direction") or "").strip().lower() != "outbound" and str(item.get("text") or "").strip()
        ]
        current_text = text.strip()
        if current_text and (not customer_turns or customer_turns[-1] != current_text):
            customer_turns.append(current_text)
        combined_text = " ".join(customer_turns).strip()
        lowered_combined = combined_text.lower()
        lowered_current = current_text.lower()

        current_search_terms = self._ai_search_terms(current_text)
        current_product_hints = [
            hint
            for hint in SHOPPING_PRODUCT_HINTS
            if hint not in {"color", "colour", "size"} and self._text_contains_token(lowered_current, hint)
        ]
        if current_product_hints and not re.search(r"\bthe\b", lowered_current):
            current_search_terms = [term for term in current_search_terms if term not in {"premium", "budget"}]
        current_model_number_terms = self._product_model_number_terms(current_text)
        combined_search_terms = self._ai_search_terms(combined_text)
        if current_product_hints and not re.search(r"\bthe\b", lowered_current):
            combined_search_terms = [term for term in combined_search_terms if term not in {"premium", "budget"}]
        combined_model_number_terms = self._product_model_number_terms(combined_text)
        existing_product_terms = [term for term in preferences["product_terms"] if term]
        existing_product_hints = [
            term
            for term in existing_product_terms
            if term in SHOPPING_PRODUCT_HINTS and term not in {"color", "colour", "size"}
        ]
        switching_request = any(token in lowered_current for token in ("instead", "actually", "rather"))
        pronoun_follow_up = bool(re.search(r"\b(this|it|that|these|those)\b", lowered_current))
        current_non_product_topic = any(phrase in lowered_current for phrase in SHOPPING_NON_PRODUCT_TOPIC_PHRASES)
        current_product_hint_tokens = self._product_hint_token_set(current_product_hints)
        existing_product_hint_tokens = self._product_hint_token_set(existing_product_hints)
        current_product_context_terms = set(current_model_number_terms) | current_product_hint_tokens | {
            term for term in current_search_terms if term not in SHOPPING_COLOR_WORDS
        }
        existing_product_context_terms = set(existing_product_terms) | existing_product_hint_tokens
        explicit_product_request = bool(
            current_product_hints
            and (
                switching_request
                or any(phrase in lowered_current for phrase in SHOPPING_AVAILABILITY_PHRASES)
                or any(phrase in lowered_current for phrase in SHOPPING_RECOMMENDATION_PHRASES)
                or any(phrase in lowered_current for phrase in SHOPPING_SIMPLE_DISCOVERY_PHRASES)
            )
        )
        reset_for_product_switch = bool(
            explicit_product_request
            and existing_product_context_terms
            and current_product_context_terms
            and current_product_context_terms.isdisjoint(existing_product_context_terms)
        )

        if reset_for_product_switch:
            preferences["product_terms"] = self._merge_unique_texts([], current_product_hints + current_search_terms + current_model_number_terms)
        elif combined_text and not current_non_product_topic:
            preference_terms = combined_search_terms + combined_model_number_terms
            if current_product_hints and switching_request:
                preference_terms = current_product_hints + current_search_terms + current_model_number_terms
            preferences["product_terms"] = self._merge_unique_texts(preferences["product_terms"], preference_terms)

        current_colors = self._colors_in_text(lowered_current)
        combined_colors = self._colors_in_text(lowered_combined)
        if reset_for_product_switch:
            preferences["colors"] = current_colors
        else:
            preferences["colors"] = current_colors or self._merge_unique_texts(preferences["colors"], combined_colors)

        current_sizes = [match.group(1).strip() for match in SHOPPING_SIZE_PATTERN.finditer(current_text)]
        if not current_sizes and not current_non_product_topic:
            in_size_matches = [match.group(1) for match in re.finditer(r"\bin\s+([3-5][0-9](?:\.[0-9])?)\b", current_text.lower())]
            if in_size_matches and (current_product_hints or pronoun_follow_up or existing_product_terms):
                current_sizes = [in_size_matches[-1]]
        if not current_sizes and switching_request and not current_non_product_topic:
            bare_size_matches = [match.group(1) for match in re.finditer(r"\b([3-5][0-9])\b", current_text)]
            if bare_size_matches:
                current_sizes = [bare_size_matches[-1]]
        combined_sizes = [match.group(1).strip() for match in SHOPPING_SIZE_PATTERN.finditer(combined_text)]
        if reset_for_product_switch:
            preferences["sizes"] = current_sizes
        else:
            preferences["sizes"] = current_sizes or self._merge_unique_texts(preferences["sizes"], combined_sizes)

        current_use_case_terms = [phrase for phrase in SHOPPING_USE_CASE_PHRASES if phrase in lowered_current]
        combined_use_case_terms = [phrase for phrase in SHOPPING_USE_CASE_PHRASES if phrase in lowered_combined]
        if reset_for_product_switch:
            preferences["use_case_terms"] = current_use_case_terms
        else:
            preferences["use_case_terms"] = self._merge_unique_texts(
                preferences["use_case_terms"],
                combined_use_case_terms,
            )

        wants_lower_price = any(token in lowered_current for token in ("cheaper", "under ", "below ", "affordable", "budget option", "budget-friendly", "on a budget"))
        wants_higher_price = any(
            token in lowered_current
            for token in (
                "more premium",
                "higher price",
                "higher priced",
                "higher-end",
                "better option",
                "better one",
                "something better",
                "more expensive",
                "show me premium",
                "premium option",
                "premium options",
                "premium one",
                "premium version",
                "upgrade",
            )
        )
        current_budget_match = SHOPPING_BUDGET_PATTERN.search(current_text) if not current_non_product_topic else None
        if wants_higher_price and not current_non_product_topic:
            preferences["max_budget"] = ""
        elif current_budget_match:
            preferences["max_budget"] = self._normalized_decimal_string(current_budget_match.group(1))
        elif not preferences["max_budget"] and combined_text and not current_non_product_topic:
            budget_match = SHOPPING_BUDGET_PATTERN.search(combined_text)
            if budget_match:
                preferences["max_budget"] = self._normalized_decimal_string(budget_match.group(1))

        prior_outbound_text = " ".join(
            str(item.get("text") or "").strip()
            for item in recent_context
            if str(item.get("direction") or "").strip().lower() == "outbound"
        )
        price_matches = [
            self._normalized_decimal_string(match.group(1))
            for match in SHOPPING_PRICE_PATTERN.finditer(prior_outbound_text)
        ]
        if price_matches:
            preferences["last_referenced_price"] = price_matches[-1]

        if any(phrase in lowered_current for phrase in SHOPPING_RECOMMENDATION_PHRASES):
            preferences["wants_recommendation"] = True
        if any(phrase in lowered_current for phrase in SHOPPING_AVAILABILITY_PHRASES):
            preferences["wants_availability"] = True

        if wants_higher_price and not current_non_product_topic:
            preferences["price_preference"] = "higher"
        elif (wants_lower_price or preferences["max_budget"]) and not current_non_product_topic:
            preferences["price_preference"] = "lower"

        return preferences

    def _merge_unique_texts(self, existing: list[str], new_items: list[str]) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for item in [*(existing or []), *(new_items or [])]:
            normalized = str(item).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            values.append(normalized)
        return values

    def _colors_in_text(self, lowered_text: str) -> list[str]:
        return [color for color in SHOPPING_COLOR_WORDS if re.search(rf"\b{re.escape(color)}\b", lowered_text)]

    def _product_hint_token_set(self, hints: list[str]) -> set[str]:
        tokens: set[str] = set()
        for hint in hints:
            tokens.update(self._product_hint_terms(hint))
        return tokens

    def _product_model_number_terms(self, text: str) -> list[str]:
        tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
        if not tokens:
            return []

        disallowed_previous = set(AI_SEARCH_STOPWORDS) | set(SHOPPING_COLOR_WORDS) | set(SHOPPING_PRODUCT_HINTS) | {
            "aed",
            "budget",
            "below",
            "delivery",
            "dh",
            "dhs",
            "dirham",
            "dirhams",
            "eu",
            "hour",
            "hours",
            "in",
            "less",
            "minute",
            "minutes",
            "shipping",
            "size",
            "slot",
            "slots",
            "than",
            "to",
            "under",
            "up",
            "upto",
            "usd",
        }
        disallowed_next = {"day", "days", "hour", "hours", "minute", "minutes"}
        terms: list[str] = []
        seen: set[str] = set()

        for index, token in enumerate(tokens):
            if not token.isdigit():
                continue
            previous = tokens[index - 1] if index > 0 else ""
            previous_previous = tokens[index - 2] if index > 1 else ""
            next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
            if not previous or previous in disallowed_previous or next_token in disallowed_next:
                continue
            if previous in {"max", "maximum"} and (
                not previous_previous or previous_previous in AI_SEARCH_STOPWORDS or previous_previous in {"budget", "my", "price", "spend"}
            ):
                continue
            if token in seen:
                continue
            seen.add(token)
            terms.append(token)

        return terms

    def _compact_alnum_text(self, text: str) -> str:
        return "".join(char.lower() for char in str(text or "") if char.isalnum())

    def _exact_product_compact_phrase(self, specific_terms: list[str], product_hints: list[str]) -> str:
        normalized_specific_terms = [str(term).strip().lower() for term in specific_terms if str(term).strip()]
        normalized_hints = [str(term).strip().lower() for term in product_hints if str(term).strip()]
        if len(normalized_specific_terms) >= 2 or any(re.fullmatch(r"\d+(?:\.\d+)?", term) for term in normalized_specific_terms):
            return self._compact_alnum_text(" ".join(normalized_specific_terms))
        if len(normalized_specific_terms) == 1 and normalized_hints:
            return self._compact_alnum_text(f"{normalized_specific_terms[0]} {normalized_hints[0]}")
        if normalized_specific_terms:
            return self._compact_alnum_text(" ".join(normalized_specific_terms))
        return ""

    def _catalog_search_terms(self, *, text: str, preferences: dict[str, Any] | None) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()

        def add(term: str, *, expand_product_hints: bool = False) -> None:
            normalized = str(term).strip().lower()
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            terms.append(normalized)
            if expand_product_hints and normalized in SHOPPING_PRODUCT_HINTS:
                for synonym in sorted(self._product_hint_terms(normalized)):
                    if synonym != normalized:
                        add(synonym)

        add(text.strip())
        current_search_terms = self._ai_search_terms(text)
        current_model_terms = self._product_model_number_terms(text)
        current_specific_terms = [
            term
            for term in current_search_terms
            if not self._is_non_specific_product_term(term) and term not in SHOPPING_COLOR_WORDS
        ]
        if current_model_terms and current_specific_terms:
            exact_phrase_terms = current_specific_terms[:2] + [
                term for term in current_model_terms if term not in current_specific_terms[:2]
            ]
            if len(exact_phrase_terms) >= 2:
                add(" ".join(exact_phrase_terms[:3]))
        for term in current_model_terms:
            add(term)
        for term in current_search_terms:
            add(term, expand_product_hints=True)

        if isinstance(preferences, dict):
            product_terms = [str(item).strip().lower() for item in preferences.get("product_terms", []) if str(item).strip()]
            specific_product_terms = [term for term in product_terms if not self._is_non_specific_product_term(term)]
            product_model_terms = [term for term in specific_product_terms if re.fullmatch(r"\d+(?:\.\d+)?", term)]
            exact_saved_terms = [
                term for term in specific_product_terms if term not in product_model_terms and term not in SHOPPING_COLOR_WORDS
            ]
            if product_model_terms and exact_saved_terms:
                exact_phrase_terms = exact_saved_terms[:2] + [term for term in product_model_terms if term not in exact_saved_terms[:2]]
                if len(exact_phrase_terms) >= 2:
                    add(" ".join(exact_phrase_terms[:3]))
            for term in product_model_terms:
                add(term)
            if len(product_terms) >= 2:
                add(" ".join(product_terms[:2]))
            for key in ("colors", "sizes", "use_case_terms", "product_terms"):
                values = preferences.get(key, [])
                if not isinstance(values, list):
                    continue
                for item in values:
                    add(str(item), expand_product_hints=key == "product_terms")

        return terms[:16]

    def _normalized_decimal_string(self, value: Any) -> str:
        try:
            decimal_value = Decimal(str(value).strip())
        except Exception:
            return ""
        if decimal_value == decimal_value.to_integral():
            return format(decimal_value.quantize(Decimal("1")), "f")
        return format(decimal_value.normalize(), "f")

    def _money_value(self, value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value).strip())
        except Exception:
            return None

    def _is_non_specific_product_term(self, term: str) -> bool:
        normalized = str(term).strip().lower()
        if not normalized:
            return True
        if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
            return False
        use_case_tokens = {token for phrase in SHOPPING_USE_CASE_PHRASES for token in phrase.split()}
        return normalized in (
            set(AI_SEARCH_STOPWORDS)
            | set(SHOPPING_COLOR_WORDS)
            | set(SHOPPING_PRODUCT_HINTS)
            | SHOPPING_NON_SPECIFIC_PRODUCT_TERMS
            | use_case_tokens
        )

    def _catalog_item_text(self, item: dict[str, Any]) -> str:
        return " ".join(
            str(item.get(key) or "").strip().lower()
            for key in ("label", "product_name", "variant_title", "description", "category", "brand", "sku")
        )

    def _text_contains_token(self, haystack: str, token: str) -> bool:
        normalized_token = str(token).strip().lower()
        if not normalized_token:
            return False
        if re.fullmatch(r"\d+(?:\.\d+)?", normalized_token):
            return re.search(rf"(?<![\d.]){re.escape(normalized_token)}(?![\d.])", haystack) is not None
        return re.search(rf"\b{re.escape(normalized_token)}\b", haystack) is not None

    def _product_hint_terms(self, hint: str) -> set[str]:
        normalized = str(hint).strip().lower()
        if not normalized:
            return set()
        return set(SHOPPING_PRODUCT_HINT_SYNONYMS.get(normalized, {normalized}))

    def _rank_catalog_items_for_preferences(
        self,
        items: list[dict[str, Any]],
        preferences: dict[str, Any] | None,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        ranked = [dict(item) for item in items if isinstance(item, dict)]
        if not ranked:
            return []
        if not preferences:
            return ranked[:limit]

        colors = [str(item).strip().lower() for item in preferences.get("colors", []) if str(item).strip()]
        sizes = [str(item).strip() for item in preferences.get("sizes", []) if str(item).strip()]
        use_case_terms = [str(item).strip().lower() for item in preferences.get("use_case_terms", []) if str(item).strip()]
        product_terms = [str(item).strip().lower() for item in preferences.get("product_terms", []) if str(item).strip()]
        specific_product_terms = [term for term in product_terms if not self._is_non_specific_product_term(term)]
        preserve_exact_identity = bool(specific_product_terms)
        max_budget = self._money_value(preferences.get("max_budget"))
        price_preference = str(preferences.get("price_preference") or "any").strip().lower()

        if max_budget is not None and not preserve_exact_identity:
            budget_matches = [
                item
                for item in ranked
                if bool(item.get("can_sell"))
                and self._money_value(item.get("unit_price")) is not None
                and self._money_value(item.get("unit_price")) <= max_budget
            ]
            if budget_matches:
                ranked = budget_matches

        if sizes:
            size_matches = [item for item in ranked if any(self._text_contains_token(self._catalog_item_text(item), size) for size in sizes)]
            if size_matches:
                ranked = size_matches

        if colors:
            color_matches = [item for item in ranked if any(self._text_contains_token(self._catalog_item_text(item), color) for color in colors)]
            if color_matches:
                ranked = color_matches

        can_sell_matches = [item for item in ranked if bool(item.get("can_sell"))]
        if can_sell_matches and not preserve_exact_identity:
            ranked = can_sell_matches

        def sort_key(item: dict[str, Any]) -> tuple[int, Decimal, str]:
            haystack = self._catalog_item_text(item)
            score = 0
            if bool(item.get("can_sell")):
                score += 30
            available = self._money_value(item.get("available_to_sell"))
            if available is not None and available > Decimal("0"):
                score += 6
            for color in colors:
                if self._text_contains_token(haystack, color):
                    score += 12
            for size in sizes:
                if self._text_contains_token(haystack, size):
                    score += 14
            for term in use_case_terms:
                if self._text_contains_token(haystack, term):
                    score += 8
            for term in product_terms[:6]:
                if self._text_contains_token(haystack, term):
                    score += 4
            price = self._money_value(item.get("unit_price")) or Decimal("999999")
            if max_budget is not None:
                score += 18 if price <= max_budget else -12
            if price_preference == "lower":
                score += 4
            elif price_preference == "higher":
                score += 4
            price_sort = -price if price_preference == "higher" else price
            return (-score, price_sort, str(item.get("label") or item.get("product_name") or ""))

        ranked.sort(key=sort_key)
        return ranked[:limit]

    def _clarifying_shopping_question(self, preferences: dict[str, Any]) -> str:
        product_terms = [
            str(item).strip().lower()
            for item in preferences.get("product_terms", [])
            if str(item).strip() and not self._is_non_specific_product_term(str(item))
        ]
        has_product_hint = any(
            str(item).strip().lower() in SHOPPING_PRODUCT_HINTS
            for item in preferences.get("product_terms", [])
            if str(item).strip()
        )
        if not product_terms and not has_product_hint:
            return "I can help with that. What product are you looking for?"
        if not preferences.get("sizes"):
            return "I can help with that. What size do you need?"
        if not preferences.get("colors"):
            return "I can help with that. What color do you prefer?"
        if not preferences.get("max_budget"):
            return "I can help with that. What budget would you like me to stay under?"
        return "I can help with that. Do you want me to focus on a lower price, a different color, or another size?"

    def _small_talk_intent(self, message: str) -> str | None:
        normalized_source = str(message or "").strip().lower().replace("’", "'").replace("‘", "'")
        normalized = re.sub(r"[^a-z0-9' ]+", " ", normalized_source)
        normalized = " ".join(normalized.split())
        if not normalized:
            return None
        if any(re.search(pattern, normalized) for pattern in SMALL_TALK_RESET_PATTERNS):
            return "reset"
        if normalized in SMALL_TALK_GREETING_PHRASES:
            return "greeting"
        return None

    def _small_talk_reset_remainder(self, message: str) -> str:
        normalized_source = str(message or "").strip().lower().replace("’", "'").replace("‘", "'")
        normalized = re.sub(r"[^a-z0-9' ]+", " ", normalized_source)
        normalized = " ".join(normalized.split())
        for pattern in SMALL_TALK_RESET_PATTERNS:
            remainder = re.sub(pattern, "", normalized).strip()
            remainder = " ".join(remainder.split())
            if remainder != normalized:
                return remainder
        return normalized

    def _has_specific_shopping_signal(self, message: str) -> bool:
        current_preferences = self._extract_shopping_preferences(
            text=message,
            recent_context=[],
            existing_preferences={},
        )
        product_terms = [
            str(term).strip().lower()
            for term in current_preferences.get("product_terms", [])
            if str(term).strip()
        ]
        specific_product_terms = [term for term in product_terms if not self._is_non_specific_product_term(term)]
        has_product_hint = any(term in SHOPPING_PRODUCT_HINTS for term in product_terms)
        lowered = " ".join(str(message or "").lower().split())
        has_explicit_commerce_phrase = any(
            phrase in lowered
            for phrase in (
                *SHOPPING_SIMPLE_DISCOVERY_PHRASES,
                *SHOPPING_AVAILABILITY_PHRASES,
                *SHOPPING_RECOMMENDATION_PHRASES,
            )
        )
        return bool(
            current_preferences.get("colors")
            or current_preferences.get("sizes")
            or current_preferences.get("use_case_terms")
            or current_preferences.get("max_budget")
            or has_product_hint
            or current_preferences.get("wants_recommendation")
            or current_preferences.get("wants_availability")
            or (specific_product_terms and has_explicit_commerce_phrase)
        )

    def _has_non_product_topic_signal(self, message: str) -> bool:
        lowered = " ".join(str(message or "").lower().split())
        return any(phrase in lowered for phrase in SHOPPING_NON_PRODUCT_TOPIC_PHRASES)

    def _is_recoverable_technical_handoff_reason(self, reason: str) -> bool:
        normalized = str(reason or "").strip().lower()
        return normalized in {
            "ai context preparation failed",
            "ai model api key is not configured",
            "ai model request failed",
            "ai workflow is not configured",
        }

    def _deterministic_small_talk_reply(self, context_payload: dict[str, Any]) -> dict[str, Any] | None:
        current_message = str(context_payload.get("current_customer_message") or "").strip()
        if not current_message:
            return None

        small_talk_intent = self._small_talk_intent(current_message)
        if small_talk_intent == "reset":
            reset_remainder = self._small_talk_reset_remainder(current_message)
            if reset_remainder and (
                self._keyword_handoff_reason(reset_remainder)
                or self._has_specific_shopping_signal(reset_remainder)
                or self._has_non_product_topic_signal(reset_remainder)
            ):
                return None
            return {
                "reply_text": "You’re right — sorry about that. Tell me what you are looking for, your size, and any color or budget preference, and I’ll help from here.",
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "other",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_small_talk_reset"},
            }

        assistant_name = str(context_payload.get("agent", {}).get("display_name") or "the assistant").strip()
        if small_talk_intent == "greeting":
            return {
                "reply_text": f"Hi — I can help with that. Tell me what you are looking for, your size, and any color or budget preference, and {assistant_name} will check the best options for you.",
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "other",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_small_talk_greeting"},
            }

        if self._has_specific_shopping_signal(current_message):
            return None

        return None

    def _price_display(self, value: Any, currency_symbol: str, currency_code: str) -> str:
        amount = self._money_value(value)
        if amount is None:
            return "the listed price"
        prefix = str(currency_symbol or currency_code or "").strip() or "AED"
        return f"{prefix} {amount.quantize(Decimal('0.01'))}"

    def _deterministic_catalog_reply(self, context_payload: dict[str, Any]) -> dict[str, Any] | None:
        business = context_payload.get("business") or {}
        conversation = context_payload.get("conversation") or {}
        catalog = context_payload.get("catalog") or {}
        current_message = str(context_payload.get("current_customer_message") or "").strip()
        recent_messages = conversation.get("recent_messages") or []
        preferences = conversation.get("shopping_preferences") if isinstance(conversation.get("shopping_preferences"), dict) else {}
        preferences = self._extract_shopping_preferences(
            text=current_message,
            recent_context=recent_messages,
            existing_preferences=preferences,
        )
        current_preferences = self._extract_shopping_preferences(
            text=current_message,
            recent_context=[],
            existing_preferences={},
        )
        lowered_current = current_message.lower()
        current_product_hints = [
            str(item).strip().lower()
            for item in current_preferences.get("product_terms", [])
            if str(item).strip().lower() in SHOPPING_PRODUCT_HINTS
        ]
        has_order_action = any(phrase in lowered_current for phrase in SHOPPING_ORDER_ACTION_PHRASES)
        has_product_qa = bool(
            re.search(
                r"\b(is|are)\b.*\b(comfortable|comfort|material|leather|durable|waterproof|soft|lightweight|support|cushion|good for|okay for)\b",
                lowered_current,
            )
        ) or any(phrase in lowered_current for phrase in SHOPPING_PRODUCT_QA_PHRASES)
        has_non_product_topic = any(phrase in lowered_current for phrase in SHOPPING_NON_PRODUCT_TOPIC_PHRASES)
        has_discount_negotiation = any(phrase in lowered_current for phrase in SHOPPING_DISCOUNT_NEGOTIATION_PHRASES)
        has_human_request = any(phrase in lowered_current for phrase in ("talk to someone", "speak to someone"))
        has_simple_discovery = any(phrase in lowered_current for phrase in SHOPPING_SIMPLE_DISCOVERY_PHRASES)

        if has_order_action or has_product_qa or has_non_product_topic or has_discount_negotiation or has_human_request:
            return None

        shopping_signal = bool(
            current_preferences.get("wants_recommendation")
            or current_preferences.get("wants_availability")
            or current_preferences.get("max_budget")
            or current_preferences.get("colors")
            or current_preferences.get("sizes")
            or (has_simple_discovery and (current_preferences.get("product_terms") or current_preferences.get("use_case_terms")))
        )
        if not shopping_signal:
            return None

        catalog_items = [dict(item) for item in catalog.get("items") or [] if isinstance(item, dict)]
        current_product_hints = [
            str(item).strip().lower()
            for item in current_preferences.get("product_terms", [])
            if str(item).strip().lower() in SHOPPING_PRODUCT_HINTS
        ]
        current_specific_product_terms = [
            str(item).strip().lower()
            for item in current_preferences.get("product_terms", [])
            if str(item).strip().lower()
            and not self._is_non_specific_product_term(str(item))
        ]
        current_model_number_terms = [
            term for term in current_specific_product_terms if re.fullmatch(r"\d+(?:\.\d+)?", term)
        ]
        saved_specific_product_terms = [
            str(item).strip().lower()
            for item in preferences.get("product_terms", [])
            if str(item).strip() and not self._is_non_specific_product_term(str(item))
        ]
        saved_product_hints = [
            str(item).strip().lower()
            for item in preferences.get("product_terms", [])
            if str(item).strip().lower() in SHOPPING_PRODUCT_HINTS
        ]
        pronoun_follow_up = bool(re.search(r"\b(this|it|that|these|those)\b", lowered_current))
        effective_specific_product_terms = current_specific_product_terms
        effective_product_hints = current_product_hints
        if pronoun_follow_up and not effective_specific_product_terms and saved_specific_product_terms:
            effective_specific_product_terms = saved_specific_product_terms
        if pronoun_follow_up and not effective_product_hints and saved_product_hints:
            effective_product_hints = saved_product_hints
        if pronoun_follow_up and not effective_specific_product_terms and not effective_product_hints:
            return {
                "reply_text": "I can help with that. Which item are you asking about?",
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "availability",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_pronoun_clarify"},
            }
        combined_product_terms = [
            str(item).strip().lower()
            for item in preferences.get("product_terms", [])
            if str(item).strip()
        ]
        has_combined_product_context = bool(
            any(not self._is_non_specific_product_term(term) for term in combined_product_terms)
            or any(term in SHOPPING_PRODUCT_HINTS for term in combined_product_terms)
        )
        underconstrained_current_turn = bool(
            not has_combined_product_context
            and (
                current_preferences.get("colors")
                or current_preferences.get("sizes")
                or current_preferences.get("max_budget")
                or current_preferences.get("wants_availability")
                or current_preferences.get("wants_recommendation")
            )
        )
        if underconstrained_current_turn:
            return {
                "reply_text": self._clarifying_shopping_question(preferences),
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "recommendation",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_underconstrained_clarify"},
            }
        exact_product_compact_phrase = self._exact_product_compact_phrase(effective_specific_product_terms, effective_product_hints)
        exact_named_request = bool(
            exact_product_compact_phrase
            and (
                pronoun_follow_up
                or re.search(r"\bthe\b", lowered_current)
                or len(effective_specific_product_terms) >= 2
                or any(re.fullmatch(r"\d+(?:\.\d+)?", term) for term in effective_specific_product_terms)
            )
        )
        strict_constraints_present = bool(preferences.get("colors") or preferences.get("sizes") or effective_product_hints or effective_specific_product_terms)
        candidate_items = catalog_items
        if strict_constraints_present:
            colors = [str(item).strip().lower() for item in preferences.get("colors", []) if str(item).strip()]
            sizes = [str(item).strip() for item in preferences.get("sizes", []) if str(item).strip()]
            exact_compact_matches = [
                item
                for item in candidate_items
                if exact_product_compact_phrase and exact_product_compact_phrase in self._compact_alnum_text(self._catalog_item_text(item))
            ]
            if exact_compact_matches:
                candidate_items = exact_compact_matches
            elif exact_named_request:
                candidate_items = []
            else:
                require_all_specific_terms = bool(
                    any(re.fullmatch(r"\d+(?:\.\d+)?", term) for term in effective_specific_product_terms)
                    or len(effective_specific_product_terms) >= 2
                )
                if effective_specific_product_terms:
                    match_fn = all if require_all_specific_terms else any
                    candidate_items = [
                        item
                        for item in candidate_items
                        if match_fn(
                            self._text_contains_token(self._catalog_item_text(item), term)
                            for term in effective_specific_product_terms
                        )
                    ]
                if effective_product_hints:
                    candidate_items = [
                        item
                        for item in candidate_items
                        if any(
                            any(self._text_contains_token(self._catalog_item_text(item), token) for token in self._product_hint_terms(hint))
                            for hint in effective_product_hints
                        )
                    ]
            if colors:
                candidate_items = [
                    item for item in candidate_items if any(self._text_contains_token(self._catalog_item_text(item), color) for color in colors)
                ]
            if sizes:
                candidate_items = [
                    item for item in candidate_items if any(self._text_contains_token(self._catalog_item_text(item), size) for size in sizes)
                ]
            if not candidate_items and catalog_items:
                return {
                    "reply_text": "I do not currently see a matching option with those details. If you want, I can suggest a similar option or help with another color or size.",
                    "handoff_required": False,
                    "handoff_reason": "",
                    "order_status": None,
                    "latest_intent": "availability",
                    "latest_summary": _preview(current_message),
                    "action": {"type": "none"},
                    "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_no_strict_match"},
                }

        ranked_items = self._rank_catalog_items_for_preferences(candidate_items, preferences, limit=3)
        max_budget = self._money_value(preferences.get("max_budget"))
        budget_scope_items = [item for item in candidate_items if bool(item.get("can_sell"))]
        has_budget_match = (
            max_budget is None
            or any(
                self._money_value(item.get("unit_price")) is not None
                and self._money_value(item.get("unit_price")) <= max_budget
                for item in budget_scope_items
            )
        )
        currency_symbol = str(business.get("currency_symbol") or "").strip()
        currency_code = str(business.get("currency_code") or "AED").strip()

        if not ranked_items:
            return {
                "reply_text": self._clarifying_shopping_question(preferences),
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "recommendation",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_clarify"},
            }

        sellable_ranked_items = [item for item in ranked_items if bool(item.get("can_sell"))]
        if sellable_ranked_items:
            ranked_items = sellable_ranked_items
        else:
            top_item = ranked_items[0]
            return {
                "reply_text": (
                    f"I do not currently see {str(top_item.get('label') or top_item.get('product_name') or 'that item').strip()} ready to sell right now. "
                    "If you want, I can suggest a similar option or help with another color or size."
                ),
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "availability",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_out_of_stock"},
            }

        if max_budget is not None and not has_budget_match:
            top_item = ranked_items[0]
            return {
                "reply_text": (
                    f"I do not currently see an in-stock option within {self._price_display(max_budget, currency_symbol, currency_code)}. "
                    f"The closest match I found is {str(top_item.get('label') or top_item.get('product_name') or 'that option').strip()} at "
                    f"{self._price_display(top_item.get('unit_price'), currency_symbol, currency_code)}. "
                    "Would you like to see that option, or should I look for another color or size?"
                ),
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "recommendation",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_budget_gap"},
            }

        wants_recommendation = (
            bool(current_preferences.get("wants_recommendation"))
            or bool(current_preferences.get("max_budget"))
            or str(current_preferences.get("price_preference") or "") == "lower"
        )
        if wants_recommendation:
            options = ranked_items[:2]
            if len(options) == 1:
                option = options[0]
                reply_text = (
                    f"Yes — a good option is {str(option.get('label') or option.get('product_name') or 'this item').strip()} at "
                    f"{self._price_display(option.get('unit_price'), currency_symbol, currency_code)}. "
                    "It is in stock. Would you like this one, or should I show another option?"
                )
            else:
                first, second = options[0], options[1]
                reply_text = (
                    f"Yes — two good options are {str(first.get('product_name') or first.get('label') or 'Option 1').strip()} at "
                    f"{self._price_display(first.get('unit_price'), currency_symbol, currency_code)} and "
                    f"{str(second.get('product_name') or second.get('label') or 'Option 2').strip()} at "
                    f"{self._price_display(second.get('unit_price'), currency_symbol, currency_code)}. "
                    "Both are in stock. Would you like the first option or the second one?"
                )
            return {
                "reply_text": reply_text,
                "handoff_required": False,
                "handoff_reason": "",
                "order_status": None,
                "latest_intent": "recommendation",
                "latest_summary": _preview(current_message),
                "action": {"type": "none"},
                "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_recommendation"},
            }

        top_item = ranked_items[0]
        description = str(top_item.get("description") or "").strip()
        detail = f" {description}." if description else ""
        return {
            "reply_text": (
                f"Yes — {str(top_item.get('label') or top_item.get('product_name') or 'that item').strip()} is available at "
                f"{self._price_display(top_item.get('unit_price'), currency_symbol, currency_code)}.{detail} "
                "Would you like this option, or should I suggest something else?"
            ),
            "handoff_required": False,
            "handoff_reason": "",
            "order_status": None,
            "latest_intent": "availability",
            "latest_summary": _preview(current_message),
            "action": {"type": "none"},
            "ai_metadata": {"ai_runtime": "easy_ecom", "response_strategy": "deterministic_catalog_availability"},
        }

    def _build_ai_model_messages(self, context_payload: dict[str, Any]) -> list[dict[str, str]]:
        system_prompt = (
            "You are the EasyEcom native AI sales assistant runtime. "
            "Act like a warm, capable human sales assistant for the tenant. "
            "EasyEcom facts are the only source of truth for stock, price, policy, and order state. "
            "Keep replies short, natural, and specific. "
            "Acknowledge the customer's request before giving details. "
            "Ask at most one focused follow-up question when required. "
            "Do not repeat a greeting unless the customer starts a new greeting. "
            "Do not invent products, stock, prices, delivery promises, refunds, or payment outcomes. "
            "If the catalog context is empty or ambiguous, ask a clarifying question instead of guessing. "
            "Return exactly one JSON object and no markdown. "
            "Required keys: reply_text, handoff_required, handoff_reason, latest_intent, latest_summary, action. "
            "Allowed latest_intent values: product_qa, recommendation, availability, cart_building, order_confirmation, discount, handoff, other. "
            "action must be {\"type\":\"none\"} unless the backend should do something. "
            "To request handoff, use {\"type\":\"handoff\",\"reason\":\"...\"}. "
            "To confirm an order, use {\"type\":\"confirm_order\",\"customer_confirmed\":true,\"confirmation_text\":\"...\",\"customer\":{\"name\":\"...\",\"phone\":\"...\",\"email\":\"...\",\"address\":\"...\"},\"lines\":[{\"variant_id\":\"...\",\"quantity\":\"1\",\"unit_price\":\"...\",\"discount_amount\":\"0\"}],\"location_id\":\"...\",\"notes\":\"...\"}. "
            "Only use confirm_order when the customer explicitly confirms and all required customer fields are present."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": self._build_ai_context_message(context_payload)},
        ]
        messages.extend(self._conversation_messages_for_model(context_payload))
        current_message = str(context_payload.get("current_customer_message", "")).strip()
        if current_message and (
            not messages
            or messages[-1]["role"] != "user"
            or messages[-1]["content"].strip() != current_message
        ):
            messages.append({"role": "user", "content": current_message})
        return messages

    def _build_ai_context_message(self, context_payload: dict[str, Any]) -> str:
        business = context_payload.get("business") or {}
        agent = context_payload.get("agent") or {}
        customer = context_payload.get("customer") or {}
        conversation = context_payload.get("conversation") or {}
        stock_location = context_payload.get("stock_location") or {}
        catalog = context_payload.get("catalog") or {}
        items = catalog.get("items") or []
        shopping_preferences = conversation.get("shopping_preferences") or {}
        faq_entries = agent.get("faq_entries") or []
        guardrails = context_payload.get("guardrails") or []

        lines = [
            f"Business name: {str(business.get('business_name') or '').strip() or 'Unknown business'}",
            f"Assistant display name: {str(agent.get('display_name') or '').strip() or 'Store assistant'}",
            f"Brand voice/persona: {str(agent.get('persona_prompt') or '').strip() or 'Not configured'}",
            f"Store policy: {str(agent.get('store_policy') or '').strip() or 'Not configured'}",
            f"Fallback handoff message: {str(agent.get('handoff_message') or DEFAULT_HANDOFF_MESSAGE).strip()}",
            f"Conversation status: {str(conversation.get('status') or 'open').strip()}",
            f"Latest conversation summary: {str(conversation.get('latest_summary') or '').strip() or 'None'}",
            f"Latest conversation intent: {str(conversation.get('latest_intent') or '').strip() or 'unknown'}",
            f"Stock location: {str(stock_location.get('location_name') or '').strip() or 'Default location'}",
            f"Customer name: {str(customer.get('name') or '').strip() or 'Unknown'}",
            f"Customer phone: {str(customer.get('phone') or '').strip() or 'Unknown'}",
            f"Customer email: {str(customer.get('email') or '').strip() or 'Unknown'}",
            f"Customer address: {str(customer.get('address') or '').strip() or 'Unknown'}",
        ]

        if faq_entries:
            lines.append("Approved FAQ:")
            for item in faq_entries[:6]:
                question = str(item.get("question") or "").strip()
                answer = str(item.get("answer") or "").strip()
                if question or answer:
                    lines.append(f"- Q: {question or 'Unknown'} | A: {answer or 'Unknown'}")

        if shopping_preferences:
            lines.append("Structured shopping preferences:")
            for key in ("product_terms", "colors", "sizes", "use_case_terms"):
                values = [str(item).strip() for item in shopping_preferences.get(key, []) if str(item).strip()]
                if values:
                    lines.append(f"- {key}: {', '.join(values[:6])}")
            if str(shopping_preferences.get("max_budget") or "").strip():
                lines.append(f"- max_budget: {str(shopping_preferences.get('max_budget')).strip()}")
            if str(shopping_preferences.get("price_preference") or "").strip():
                lines.append(f"- price_preference: {str(shopping_preferences.get('price_preference')).strip()}")

        lines.append("Catalog matches:")
        if items:
            for item in items[:8]:
                label = str(item.get("label") or item.get("product_name") or "Unknown item").strip()
                description = str(item.get("description") or '').strip() or 'No description'
                price = str(item.get("unit_price") or 'unknown').strip()
                min_price = str(item.get("min_price") or 'unknown').strip()
                available = str(item.get("available_to_sell") or '0').strip()
                sku = str(item.get("sku") or '').strip() or 'n/a'
                can_sell = bool(item.get("can_sell"))
                lines.append(
                    f"- {label} | sku={sku} | unit_price={price} | min_price={min_price} | available_to_sell={available} | can_sell={'yes' if can_sell else 'no'} | description={description}"
                )
        else:
            lines.append("- No confident catalog matches were found for this message. Ask a short clarifying question before recommending a product.")

        if guardrails:
            lines.append("Guardrails:")
            for rule in guardrails:
                if str(rule).strip():
                    lines.append(f"- {str(rule).strip()}")

        return "\n".join(lines)

    def _conversation_messages_for_model(self, context_payload: dict[str, Any]) -> list[dict[str, str]]:
        conversation = context_payload.get("conversation") or {}
        recent_messages = conversation.get("recent_messages") or []
        messages: list[dict[str, str]] = []
        for item in recent_messages:
            direction = str(item.get("direction") or "").strip().lower()
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            role = "assistant" if direction == "outbound" else "user"
            messages.append({"role": role, "content": text})
        return messages

    def _call_ai_model(self, messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]]:
        response = httpx.post(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openai_model,
                "messages": messages,
                "temperature": 0.35,
                "max_tokens": 900,
            },
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not choices:
            raise ValueError("AI model response did not include choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise ValueError("AI model response did not include a message")
        content = message.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
        return str(content), payload

    def _parse_ai_model_response(self, model_text: str) -> dict[str, Any]:
        content = model_text.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        payload = self._extract_json_object(content)
        if payload is not None:
            return payload
        return {
            "reply_text": "",
            "handoff_required": True,
            "handoff_reason": "AI model returned invalid structured output",
            "latest_intent": "handoff",
            "latest_summary": _preview(content),
            "action": {"type": "none"},
            "ai_metadata": {
                "parse_status": "invalid_json",
                "raw_response_preview": _preview(content, limit=500),
            },
        }

    def _extract_json_object(self, content: str) -> dict[str, Any] | None:
        decoder = json.JSONDecoder()
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            return payload
        for index, character in enumerate(content):
            if character != "{":
                continue
            try:
                candidate, _end = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                return candidate
        return None

    def _normalize_ai_reply(self, payload: dict[str, Any], *, fallback_message: str, text: str) -> dict[str, Any]:
        reply_text = str(payload.get("reply_text") or payload.get("reply") or payload.get("message") or "").strip()
        handoff_required = self._boolish(payload.get("handoff_required"))
        handoff_reason = str(payload.get("handoff_reason") or "").strip()
        latest_intent = str(payload.get("latest_intent") or "other").strip().lower()
        if latest_intent not in AI_ALLOWED_INTENTS:
            latest_intent = "other"
        latest_summary = str(payload.get("latest_summary") or "").strip() or _preview(text)
        action = payload.get("action") if isinstance(payload.get("action"), dict) else {"type": "none"}
        if not reply_text:
            reply_text = fallback_message
            handoff_required = True
            handoff_reason = handoff_reason or "AI model returned an empty reply"
            latest_intent = "handoff"
        if handoff_required and not handoff_reason:
            handoff_reason = "AI model requested handoff"
        return {
            "reply_text": reply_text,
            "handoff_required": handoff_required,
            "handoff_reason": handoff_reason,
            "order_status": payload.get("order_status"),
            "latest_intent": latest_intent,
            "latest_summary": latest_summary,
            "action": action,
            "ai_metadata": dict((payload.get("ai_metadata") or {}) | {"model_reply": _json_safe(payload)}),
        }

    def _maybe_execute_ai_action(
        self,
        *,
        client_id: str,
        conversation_id: str,
        context_payload: dict[str, Any],
        reply_payload: dict[str, Any],
        fallback_message: str,
    ) -> dict[str, Any]:
        action = reply_payload.get("action") if isinstance(reply_payload.get("action"), dict) else {"type": "none"}
        action_type = str(action.get("type", "none")).strip().lower()
        if action_type in {"", "none"}:
            return reply_payload
        if action_type == "handoff":
            reply_payload["handoff_required"] = True
            reply_payload["handoff_reason"] = str(action.get("reason", "")).strip() or reply_payload.get("handoff_reason") or "AI model requested handoff"
            reply_payload["latest_intent"] = "handoff"
            return reply_payload
        if action_type != "confirm_order":
            return self._ai_handoff_payload(
                fallback_message=fallback_message,
                handoff_reason=f"Unsupported AI action requested: {action_type}",
                latest_summary=reply_payload.get("latest_summary", ""),
                metadata={"model_status": "unsupported_action", "action": _json_safe(action)},
            )

        if not context_payload.get("agent", {}).get("allowed_actions", {}).get("order_confirmation", True):
            return self._ai_handoff_payload(
                fallback_message=fallback_message,
                handoff_reason="AI order confirmation is disabled for this tenant",
                latest_summary=reply_payload.get("latest_summary", ""),
                metadata={"model_status": "order_confirmation_disabled", "action": _json_safe(action)},
            )

        lines = action.get("lines") if isinstance(action.get("lines"), list) else []
        customer = action.get("customer") if isinstance(action.get("customer"), dict) else {}
        try:
            result = self.tool_confirm_order_from_chat(
                client_id=client_id,
                conversation_id=conversation_id,
                customer=customer,
                lines=[
                    {
                        "variant_id": str(item.get("variant_id", "")).strip(),
                        "quantity": as_decimal(item.get("quantity", "0")),
                        "unit_price": as_optional_decimal(item.get("unit_price")),
                        "discount_amount": as_decimal(item.get("discount_amount", "0")),
                    }
                    for item in lines
                    if isinstance(item, dict)
                ],
                customer_confirmed=self._boolish(action.get("customer_confirmed")),
                confirmation_text=str(action.get("confirmation_text", "")).strip(),
                location_id=str(action.get("location_id") or context_payload.get("stock_location", {}).get("location_id") or "").strip() or None,
                notes=str(action.get("notes", "")).strip(),
            )
        except Exception as exc:
            message = getattr(exc, "message", str(exc))
            return self._ai_handoff_payload(
                fallback_message=fallback_message,
                handoff_reason=f"AI order validation failed: {message[:400]}",
                latest_summary=reply_payload.get("latest_summary", ""),
                metadata={"model_status": "order_validation_failed", "action": _json_safe(action)},
            )

        order = result.get("order", {})
        reply_payload["order_status"] = str(order.get("status", "confirmed") or "confirmed")
        reply_payload["latest_intent"] = "order_confirmation"
        reply_payload["ai_metadata"] = dict(
            (reply_payload.get("ai_metadata") or {})
            | {
                "action_executed": "confirm_order",
                "sales_order_id": str(order.get("sales_order_id", "")),
                "order_number": str(order.get("order_number", "")),
            }
        )
        return reply_payload

    def _ai_handoff_payload(
        self,
        *,
        fallback_message: str,
        handoff_reason: str,
        latest_summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "reply_text": fallback_message,
            "handoff_required": True,
            "handoff_reason": handoff_reason,
            "order_status": None,
            "latest_intent": "handoff",
            "latest_summary": latest_summary,
            "ai_metadata": dict({"ai_runtime": "easy_ecom"} | (metadata or {})),
        }

    def _boolish(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)

    def _audit_ai_model_step(
        self,
        *,
        client_id: str,
        conversation_id: str,
        inbound_message_id: str,
        request_json: dict[str, Any],
        response_json: dict[str, Any],
        status: str = "succeeded",
        error_message: str = "",
    ) -> None:
        with self._session_factory() as session:
            self._record_tool_call(
                session,
                client_id,
                conversation_id,
                "easy_ecom.ai.model",
                dict(request_json | {"inbound_message_id": inbound_message_id}),
                response_json,
                status=status,
                error_message=error_message,
            )
            session.commit()

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
        *,
        status: str = "succeeded",
        error_message: str = "",
    ) -> None:
        now = now_utc()
        session.add(
            AIToolCallModel(
                ai_tool_call_id=new_uuid(),
                client_id=client_id,
                ai_conversation_id=conversation_id,
                tool_name=tool_name,
                status=status,
                request_json=_json_safe(request_json),
                response_json=_json_safe(response_json),
                error_message=error_message[:1000],
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

    def _validate_public_origin(
        self,
        origin: str,
        allowed_origins: list[str],
        *,
        trusted_origins: set[str] | None = None,
    ) -> None:
        normalized_origin = _normalize_origin(origin)
        normalized_trusted = {_normalize_origin(item) for item in trusted_origins or set() if str(item).strip()}
        if normalized_origin and normalized_origin in normalized_trusted:
            return
        normalized_allowed = {_normalize_origin(item) for item in allowed_origins if str(item).strip()}
        if "*" in normalized_allowed:
            return
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

    def _require_ai_assistant_access(self, user: AuthenticatedUser) -> None:
        if (
            "AI Assistant" not in user.allowed_pages
            and "Settings" not in user.allowed_pages
            and "SUPER_ADMIN" not in user.roles
        ):
            raise ApiException(status_code=403, code="ACCESS_DENIED", message="Access denied for AI Assistant")

    def _internal_user(self, client_id: str) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=None,  # type: ignore[arg-type]
            client_id=client_id,
            name="EasyEcom AI Agent",
            email="ai-agent@system.easy-ecom",
            business_name=None,
            roles=["CLIENT_OWNER"],
            allowed_pages=["Sales", "Catalog", "Inventory", "Customers", "AI Assistant", "Settings"],
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

    def _chat_link(self, *, api_base_url: str, widget_key: str) -> str:
        return f"{api_base_url.rstrip('/')}/ai/chat/public/{widget_key}"

    def _widget_script(self, *, api_base_url: str, widget_key: str) -> str:
        base = api_base_url.rstrip("/")
        return (
            '<script src="{base}/ai/chat/widget.js" '
            'data-easy-ecom-widget-key="{widget_key}" async></script>'
        ).format(base=base, widget_key=widget_key)
