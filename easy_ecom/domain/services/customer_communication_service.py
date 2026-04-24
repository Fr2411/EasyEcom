from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
import re
from typing import Any

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import (
    AssistantPlaybookModel,
    AssistantRunModel,
    AssistantToolCallModel,
    CategoryModel,
    ClientModel,
    CustomerChannelModel,
    CustomerConversationModel,
    CustomerMessageModel,
    CustomerModel,
    InventoryLedgerModel,
    LocationModel,
    ProductModel,
    ProductVariantModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SupplierModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.commerce_service import (
    MONEY_QUANTUM,
    ZERO,
    SalesService,
    as_decimal,
    as_optional_decimal,
    build_variant_label,
    normalize_email,
    normalize_phone,
)


GROUNDING_TOOLS = {
    "search_catalog_variants",
    "get_variant_availability",
    "get_variant_price",
    "get_product_recommendations",
}

CATALOG_PRICE_RE = re.compile(r"\b(price|cost|how much|rate|unit price)\b")
CATALOG_STOCK_RE = re.compile(r"\b(available|availability|stock|in stock|do you have|do u have)\b")
CATALOG_ORDER_RE = re.compile(r"\b(order|buy|purchase|reserve|book it|take it)\b")
CATALOG_RECOMMENDATION_RE = re.compile(
    r"\b(recommend|suggest|best|which|what should i buy|looking for|need help choosing|need food|need shoes?|need sneakers?)\b"
)
CATALOG_SEARCH_STOPWORDS = {
    "a",
    "about",
    "and",
    "any",
    "are",
    "available",
    "availability",
    "buy",
    "can",
    "choosing",
    "cost",
    "do",
    "for",
    "have",
    "hello",
    "hey",
    "hi",
    "how",
    "in",
    "is",
    "it",
    "item",
    "much",
    "need",
    "of",
    "order",
    "please",
    "price",
    "product",
    "purchase",
    "rate",
    "recommend",
    "size",
    "stock",
    "suggest",
    "the",
    "there",
    "this",
    "to",
    "u",
    "want",
    "what",
    "whats",
    "you",
}


@dataclass(frozen=True)
class CatalogGrounding:
    query: str
    tool_names: tuple[str, ...]
    search_result: dict[str, Any]
    availability_result: dict[str, Any] | None = None
    price_result: dict[str, Any] | None = None

INDUSTRY_TEMPLATES: dict[str, dict[str, Any]] = {
    "general_retail": {
        "questions": ["product preference", "budget", "quantity needed"],
        "safety": ["Do not invent policies or availability."],
    },
    "pet_food": {
        "questions": ["pet type", "breed or size", "age", "allergies", "current diet", "health concerns"],
        "safety": [
            "Never diagnose medical issues.",
            "For symptoms, medication, disease, allergies, or serious health concerns, recommend a veterinarian.",
        ],
    },
    "fashion": {
        "questions": ["size", "color", "occasion", "budget", "fit preference"],
        "safety": ["Confirm size/color variant before stock or price answers."],
    },
    "shoe_store": {
        "questions": ["shoe size", "intended use", "color or style", "fit preference", "budget"],
        "safety": [
            "Confirm size and color before stock or price promises.",
            "Do not claim orthopedic or medical benefits unless tenant data explicitly supports it.",
        ],
    },
    "electronics": {
        "questions": ["device model", "compatibility need", "warranty preference", "budget"],
        "safety": ["Do not claim compatibility unless product data or tenant policy supports it."],
    },
    "cosmetics": {
        "questions": ["skin type", "sensitivity", "allergies", "desired result"],
        "safety": ["Do not give medical claims or guaranteed results."],
    },
    "grocery": {
        "questions": ["quantity", "brand preference", "delivery timing", "dietary restrictions"],
        "safety": ["Do not claim ingredient or allergy details unless product data supports them."],
    },
}

DEFAULT_POLICIES: dict[str, Any] = {
    "delivery": "",
    "returns": "",
    "payment": "",
    "warranty": "",
    "discounts": "",
}

DEFAULT_ESCALATION_RULES: dict[str, Any] = {
    "angry_customer": True,
    "medical_or_health": True,
    "legal_or_safety": True,
    "refund_dispute": True,
    "high_value_order": True,
    "unavailable_product": True,
}


def _require_page(user: AuthenticatedUser, page: str) -> None:
    if page not in user.allowed_pages and "SUPER_ADMIN" not in user.roles:
        raise ApiException(status_code=403, code="ACCESS_DENIED", message=f"Access denied for {page}")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(MONEY_QUANTUM) if value.as_tuple().exponent < -3 else value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def _preview(text: str, limit: int = 280) -> str:
    normalized = " ".join(text.strip().split())
    return normalized[:limit]


class NvidiaChatClient:
    def __init__(self) -> None:
        self.base_url = settings.nvidia_base_url.rstrip("/")
        self.model = settings.nvidia_model
        self.api_key = settings.nvidia_api_key
        self.timeout_seconds = settings.ai_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return settings.ai_provider == "nvidia" and bool(self.base_url and self.model and self.api_key)

    def create_chat_completion(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.is_configured:
            raise ApiException(
                status_code=503,
                code="AI_PROVIDER_NOT_CONFIGURED",
                message="NVIDIA AI provider is not configured",
            )
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.35,
                "max_tokens": 650,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


class CustomerCommunicationService:
    def __init__(self, session_factory: sessionmaker[Session], ai_client: NvidiaChatClient | None = None) -> None:
        self._session_factory = session_factory
        self._ai_client = ai_client or NvidiaChatClient()
        self._sales = SalesService(session_factory)

    def overview(self, user: AuthenticatedUser):
        from easy_ecom.api.schemas.common import ModuleOverviewResponse, OverviewMetric

        _require_page(user, "Customer Communication")
        with self._session_factory() as session:
            channels = self._count(session, CustomerChannelModel, user.client_id)
            conversations = self._count(session, CustomerConversationModel, user.client_id)
            escalated = self._count_where(
                session,
                CustomerConversationModel,
                user.client_id,
                CustomerConversationModel.status == "escalated",
            )
            return ModuleOverviewResponse(
                module="customer_communication",
                status="foundation",
                summary="AI customer conversations are grounded in tenant catalog, pricing, stock, and assistant playbook rules.",
                metrics=[
                    OverviewMetric(label="Channels", value=str(channels)),
                    OverviewMetric(label="Conversations", value=str(conversations)),
                    OverviewMetric(label="Escalations", value=str(escalated)),
                    OverviewMetric(label="AI Provider", value="NVIDIA" if self._ai_client.is_configured else "Not configured"),
                ],
            )

    def workspace(self, user: AuthenticatedUser, *, conversation_id: str | None = None) -> dict[str, Any]:
        _require_page(user, "Customer Communication")
        with self._session_factory() as session:
            playbook = self._get_or_create_playbook(session, user.client_id)
            channels = list(
                session.execute(
                    select(CustomerChannelModel)
                    .where(CustomerChannelModel.client_id == user.client_id)
                    .order_by(CustomerChannelModel.created_at.desc())
                ).scalars()
            )
            conversations = self._conversation_rows(session, user.client_id, limit=30)
            active = None
            if conversation_id:
                active_record = self._get_conversation(session, user.client_id, conversation_id)
                active = self._conversation_detail(session, active_record)
            elif conversations:
                active = self._conversation_detail(session, conversations[0][0])
            session.commit()
            return {
                "playbook": self._playbook_payload(playbook),
                "channels": [self._channel_payload(channel) for channel in channels],
                "conversations": [self._conversation_summary_payload(*row) for row in conversations],
                "active_conversation": active,
            }

    def update_playbook(self, user: AuthenticatedUser, payload: dict[str, Any]) -> dict[str, Any]:
        _require_page(user, "Customer Communication")
        with self._session_factory() as session:
            playbook = self._get_or_create_playbook(session, user.client_id)
            business_type = str(payload.get("business_type", "general_retail")).strip() or "general_retail"
            playbook.business_type = business_type
            playbook.brand_personality = str(payload.get("brand_personality", "friendly")).strip() or "friendly"
            playbook.custom_instructions = str(payload.get("custom_instructions", "")).strip()
            playbook.forbidden_claims = str(payload.get("forbidden_claims", "")).strip()
            playbook.sales_goals_json = dict(payload.get("sales_goals") or {})
            playbook.policy_json = {**DEFAULT_POLICIES, **dict(payload.get("policies") or {})}
            playbook.escalation_rules_json = {**DEFAULT_ESCALATION_RULES, **dict(payload.get("escalation_rules") or {})}
            playbook.industry_template_json = INDUSTRY_TEMPLATES.get(business_type, INDUSTRY_TEMPLATES["general_retail"])
            session.commit()
            session.refresh(playbook)
            return self._playbook_payload(playbook)

    def create_channel(self, user: AuthenticatedUser, payload: dict[str, Any]) -> dict[str, Any]:
        _require_page(user, "Customer Communication")
        with self._session_factory() as session:
            channel = CustomerChannelModel(
                channel_id=new_uuid(),
                client_id=user.client_id,
                provider=str(payload.get("provider", "website")).strip() or "website",
                display_name=str(payload.get("display_name", "")).strip(),
                status=str(payload.get("status", "active")).strip() or "active",
                external_account_id=str(payload.get("external_account_id", "")).strip(),
                webhook_key=f"cc_{new_uuid().replace('-', '')}",
                default_location_id=payload.get("default_location_id") or None,
                auto_send_enabled=bool(payload.get("auto_send_enabled", True)),
                config_json=dict(payload.get("config") or {}),
                created_by_user_id=user.user_id,
            )
            if not channel.external_account_id:
                channel.external_account_id = str(channel.channel_id)
            session.add(channel)
            session.commit()
            session.refresh(channel)
            return self._channel_payload(channel)

    def update_channel(self, user: AuthenticatedUser, channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_page(user, "Customer Communication")
        with self._session_factory() as session:
            channel = session.execute(
                select(CustomerChannelModel).where(
                    CustomerChannelModel.client_id == user.client_id,
                    CustomerChannelModel.channel_id == channel_id,
                )
            ).scalar_one_or_none()
            if channel is None:
                raise ApiException(status_code=404, code="CHANNEL_NOT_FOUND", message="Customer channel not found")
            channel.provider = str(payload.get("provider", channel.provider)).strip() or channel.provider
            channel.display_name = str(payload.get("display_name", channel.display_name)).strip() or channel.display_name
            channel.status = str(payload.get("status", channel.status)).strip() or channel.status
            channel.external_account_id = str(payload.get("external_account_id", channel.external_account_id)).strip() or str(channel.channel_id)
            channel.default_location_id = payload.get("default_location_id") or None
            channel.auto_send_enabled = bool(payload.get("auto_send_enabled", channel.auto_send_enabled))
            channel.config_json = dict(payload.get("config") or {})
            session.commit()
            session.refresh(channel)
            return self._channel_payload(channel)

    def receive_public_message(
        self,
        *,
        channel_key: str,
        external_sender_id: str,
        message_text: str,
        sender_name: str = "",
        sender_phone: str = "",
        sender_email: str = "",
        provider_event_id: str = "",
        metadata: dict[str, Any] | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            channel = session.execute(
                select(CustomerChannelModel).where(
                    CustomerChannelModel.webhook_key == channel_key,
                    CustomerChannelModel.status == "active",
                )
            ).scalar_one_or_none()
            if channel is None:
                raise ApiException(status_code=404, code="CHANNEL_NOT_FOUND", message="Customer channel not found")
            if provider_event_id:
                existing = session.execute(
                    select(CustomerMessageModel).where(
                        CustomerMessageModel.client_id == channel.client_id,
                        CustomerMessageModel.provider_event_id == provider_event_id,
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    conversation = self._get_conversation(session, str(existing.client_id), str(existing.conversation_id))
                    outbound = self._latest_outbound_for_inbound(session, conversation)
                    return {
                        "conversation": self._conversation_summary_payload(conversation, channel),
                        "inbound_message": self._message_payload(existing),
                        "outbound_message": self._message_payload(outbound) if outbound else None,
                        "assistant_run": None,
                    }

            conversation = self._get_or_create_conversation(
                session,
                channel=channel,
                external_sender_id=external_sender_id,
                sender_name=sender_name,
                sender_phone=sender_phone,
                sender_email=sender_email,
            )
            inbound = self._create_message(
                session,
                channel=channel,
                conversation=conversation,
                direction="inbound",
                sender_role="customer",
                message_text=message_text,
                provider_event_id=provider_event_id,
                metadata=metadata or {},
                raw_payload=raw_payload,
                outbound_status="received",
            )
            channel.last_inbound_at = now_utc()
            conversation.last_message_preview = _preview(message_text)
            conversation.last_message_at = now_utc()
            session.flush()

            run = None
            outbound = None
            if channel.auto_send_enabled:
                run, outbound = self._run_assistant(session, channel=channel, conversation=conversation, inbound=inbound)
            session.commit()
            return {
                "conversation": self._conversation_summary_payload(conversation, channel),
                "inbound_message": self._message_payload(inbound),
                "outbound_message": self._message_payload(outbound) if outbound else None,
                "assistant_run": self._run_payload(session, run) if run else None,
            }

    def mark_escalated(self, user: AuthenticatedUser, conversation_id: str, reason: str) -> dict[str, Any]:
        _require_page(user, "Customer Communication")
        with self._session_factory() as session:
            conversation = self._get_conversation(session, user.client_id, conversation_id)
            conversation.status = "escalated"
            conversation.escalation_reason = reason.strip() or "Manual escalation"
            session.commit()
            return self._conversation_detail(session, conversation)

    def _run_assistant(
        self,
        session: Session,
        *,
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        inbound: CustomerMessageModel,
    ) -> tuple[AssistantRunModel, CustomerMessageModel]:
        client = session.execute(select(ClientModel).where(ClientModel.client_id == channel.client_id)).scalar_one()
        playbook = self._get_or_create_playbook(session, str(channel.client_id))
        run = AssistantRunModel(
            run_id=new_uuid(),
            client_id=channel.client_id,
            conversation_id=conversation.conversation_id,
            inbound_message_id=inbound.message_id,
            status="running",
            model_provider="nvidia",
            model_name=settings.nvidia_model,
            prompt_snapshot_json={
                "business_type": playbook.business_type,
                "brand_personality": playbook.brand_personality,
                "channel_provider": channel.provider,
            },
        )
        session.add(run)
        session.flush()

        final_text = ""
        tool_names: list[str] = []
        error_message = ""
        try:
            final_text, tool_names, usage = self._complete_with_tools(
                session,
                client=client,
                playbook=playbook,
                channel=channel,
                conversation=conversation,
                inbound=inbound,
                run=run,
            )
            run.prompt_tokens = usage.get("prompt_tokens")
            run.completion_tokens = usage.get("completion_tokens")
            run.total_tokens = usage.get("total_tokens")
        except Exception as exc:
            error_message = str(exc)[:1000]
            final_text = self._safe_escalation_text(client.business_name, inbound.message_text)
            run.error_message = error_message

        if error_message:
            validation_status = "escalated"
            escalation_reason = f"Assistant model call failed: {error_message}"
        else:
            validation_status, escalation_reason = self._validate_response(
                inbound_text=inbound.message_text,
                response_text=final_text,
                tool_names=tool_names,
                playbook=playbook,
            )
        if validation_status != "ok":
            final_text = self._safe_escalation_text(client.business_name, inbound.message_text)
            conversation.status = "escalated"
            conversation.escalation_reason = escalation_reason

        outbound = self._create_message(
            session,
            channel=channel,
            conversation=conversation,
            direction="outbound",
            sender_role="assistant",
            message_text=final_text,
            provider_event_id="",
            metadata={
                "assistant_run_id": str(run.run_id),
                "validation_status": validation_status,
                "escalation_reason": escalation_reason,
            },
            raw_payload=None,
            outbound_status="sent" if validation_status == "ok" else "escalated",
        )
        channel.last_outbound_at = now_utc()
        conversation.last_message_preview = _preview(final_text)
        conversation.last_message_at = now_utc()
        conversation.latest_summary = self._conversation_summary_text(conversation.latest_summary, inbound.message_text, final_text)
        run.status = "completed" if not error_message else "failed"
        run.response_text = final_text
        run.validation_status = validation_status
        run.escalation_required = validation_status != "ok"
        run.escalation_reason = escalation_reason
        run.finished_at = now_utc()
        return run, outbound

    def _complete_with_tools(
        self,
        session: Session,
        *,
        client: ClientModel,
        playbook: AssistantPlaybookModel,
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        inbound: CustomerMessageModel,
        run: AssistantRunModel,
    ) -> tuple[str, list[str], dict[str, int | None]]:
        system_prompt = self._system_prompt(client, playbook, channel)
        history = self._conversation_history(session, str(conversation.client_id), str(conversation.conversation_id))
        tool_names: list[str] = []
        usage: dict[str, int | None] = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        playbook_reply = self._deterministic_playbook_reply(client=client, playbook=playbook, inbound_text=inbound.message_text)
        if playbook_reply:
            return playbook_reply, tool_names, usage
        catalog_grounding = self._deterministic_catalog_grounding(
            session,
            channel=channel,
            conversation=conversation,
            inbound_text=inbound.message_text,
            run=run,
        )
        if catalog_grounding is not None:
            tool_names.extend(catalog_grounding.tool_names)
            deterministic_reply = self._compose_catalog_grounded_reply(
                client=client,
                playbook=playbook,
                inbound_text=inbound.message_text,
                grounding=catalog_grounding,
            )
            if deterministic_reply:
                return deterministic_reply, tool_names, usage

        messages = [{"role": "system", "content": system_prompt}]
        if catalog_grounding is not None:
            messages.append({"role": "system", "content": self._catalog_grounding_message(catalog_grounding)})
        messages.extend([*history, {"role": "user", "content": inbound.message_text}])

        for _ in range(4):
            payload = self._ai_client.create_chat_completion(messages=messages, tools=self._tool_schemas())
            usage_payload = payload.get("usage") or {}
            usage = {
                "prompt_tokens": usage_payload.get("prompt_tokens"),
                "completion_tokens": usage_payload.get("completion_tokens"),
                "total_tokens": usage_payload.get("total_tokens"),
            }
            choice = (payload.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return str(message.get("content") or "").strip(), tool_names, usage

            messages.append(message)
            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                tool_name = str(function.get("name") or "").strip()
                arguments = self._parse_tool_arguments(function.get("arguments"))
                tool_names.append(tool_name)
                result = self._execute_tool(
                    session,
                    tool_name=tool_name,
                    arguments=arguments,
                    channel=channel,
                    conversation=conversation,
                    run=run,
                )
                self._record_tool_call(
                    session,
                    run=run,
                    conversation=conversation,
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                    provider_tool_call_id=str(tool_call.get("id") or ""),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_call.get("id") or ""),
                        "name": tool_name,
                        "content": json.dumps(_json_ready(result)),
                    }
                )
            session.flush()
        return self._safe_escalation_text(client.business_name, inbound.message_text), tool_names, usage

    def _execute_tool(
        self,
        session: Session,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        run: AssistantRunModel,
    ) -> dict[str, Any]:
        if tool_name == "search_catalog_variants":
            return self._tool_search_catalog(session, str(channel.client_id), arguments, channel)
        if tool_name == "get_variant_availability":
            return self._tool_variant_availability(session, str(channel.client_id), arguments, channel)
        if tool_name == "get_variant_price":
            return self._tool_variant_price(session, str(channel.client_id), arguments)
        if tool_name == "get_product_recommendations":
            return self._tool_recommendations(session, str(channel.client_id), arguments, channel)
        if tool_name == "lookup_customer":
            return self._tool_lookup_customer(session, str(channel.client_id), conversation)
        if tool_name == "create_draft_order":
            return self._tool_create_draft_order(session, conversation, arguments)
        if tool_name == "request_human_escalation":
            reason = str(arguments.get("reason", "Assistant requested human support")).strip()
            conversation.status = "escalated"
            conversation.escalation_reason = reason
            run.escalation_required = True
            run.escalation_reason = reason
            return {"ok": True, "status": "escalated", "reason": reason}
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}

    def _deterministic_playbook_reply(self, *, client: ClientModel, playbook: AssistantPlaybookModel, inbound_text: str) -> str:
        lower = inbound_text.lower()
        price_intent, stock_intent, _ = self._catalog_intent_flags(inbound_text)
        if self._has_escalation_risk_terms(lower):
            return self._safe_escalation_text(client.business_name, inbound_text)
        if playbook.business_type == "electronics" and self._has_electronics_safety_terms(lower):
            return self._safe_escalation_text(client.business_name, inbound_text)
        if playbook.business_type == "pet_food" and self._has_risk_terms(lower) and not (price_intent or stock_intent):
            return (
                "I’m sorry your pet is not feeling well. For vomiting, illness, allergies, medication, or sudden symptoms, "
                "please check with a veterinarian before changing food. After that, I can help narrow options if you share "
                "the pet type, age, breed or size, current diet, allergies, and any health concerns."
            )
        if playbook.business_type == "cosmetics" and self._has_allergy_terms(lower) and not (price_intent or stock_intent):
            return (
                "If you have allergies, sensitivity, burning, or a rash, please avoid applying a new product until you’ve checked "
                "with a qualified professional or the ingredient label. I can still help narrow options if you share your skin type, "
                "known allergies, sensitivity level, and desired result."
            )
        if playbook.business_type == "grocery" and self._has_allergy_terms(lower) and not (price_intent or stock_intent):
            return (
                "For allergy concerns, please verify the ingredient label and let staff confirm before purchase. "
                "Tell me the allergen you avoid, quantity, preferred brand, and delivery timing, and I’ll help narrow safe options."
            )
        if CATALOG_RECOMMENDATION_RE.search(lower) and not (price_intent or stock_intent):
            template = playbook.industry_template_json or INDUSTRY_TEMPLATES.get(playbook.business_type, INDUSTRY_TEMPLATES["general_retail"])
            questions = [str(question) for question in template.get("questions", []) if str(question).strip()]
            if playbook.business_type == "pet_food":
                return (
                    "I can help choose a suitable option. What pet is it for, and what are their age, breed or size, "
                    "current diet, allergies, and any health concerns?"
                )
            if playbook.business_type == "shoe_store":
                return (
                    "I can help narrow that down. What shoe size do you need, and is it for running, work, casual wear, "
                    "formal use, or something else? Any preferred color, fit, and budget?"
                )
            if playbook.business_type == "fashion":
                return "I can help choose something suitable. What size, color, occasion, fit preference, and budget should I use?"
            if playbook.business_type == "electronics":
                return "I can help narrow that down. What device model is it for, what compatibility need matters, and what budget or warranty preference do you have?"
            if playbook.business_type == "cosmetics":
                return "I can help shortlist options. What is your skin type, any sensitivity or allergies, desired result, and budget?"
            if playbook.business_type == "grocery":
                return "I can help with that. What quantity do you need, any preferred brand, delivery timing, and dietary restrictions?"
            if questions:
                return f"I can help with that. Could you share {self._human_join(questions[:4])}?"
        return ""

    def _record_tool_call(
        self,
        session: Session,
        *,
        run: AssistantRunModel,
        conversation: CustomerConversationModel,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        provider_tool_call_id: str = "",
    ) -> None:
        session.add(
            AssistantToolCallModel(
                tool_call_id=new_uuid(),
                client_id=run.client_id,
                run_id=run.run_id,
                conversation_id=conversation.conversation_id,
                provider_tool_call_id=provider_tool_call_id,
                tool_name=tool_name,
                tool_arguments_json=_json_ready(arguments),
                tool_result_json=_json_ready(result),
                validation_status="ok" if result.get("ok", True) else "error",
            )
        )

    def _execute_and_record_tool(
        self,
        session: Session,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        run: AssistantRunModel,
    ) -> dict[str, Any]:
        result = self._execute_tool(
            session,
            tool_name=tool_name,
            arguments=arguments,
            channel=channel,
            conversation=conversation,
            run=run,
        )
        self._record_tool_call(
            session,
            run=run,
            conversation=conversation,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
        )
        return result

    def _catalog_intent_flags(self, text: str) -> tuple[bool, bool, bool]:
        lower = text.lower()
        return bool(CATALOG_PRICE_RE.search(lower)), bool(CATALOG_STOCK_RE.search(lower)), bool(CATALOG_ORDER_RE.search(lower))

    def _needs_catalog_grounding(self, text: str) -> bool:
        return any(self._catalog_intent_flags(text))

    def _catalog_search_queries(self, text: str) -> list[str]:
        normalized = re.sub(r"[^a-z0-9+.#/-]+", " ", text.lower()).strip()
        words = [
            word.strip("./-")
            for word in normalized.split()
            if word.strip("./-") and word.strip("./-") not in CATALOG_SEARCH_STOPWORDS
        ]
        words = [word for word in words if len(word) > 1 or any(char.isdigit() for char in word)]
        queries: list[str] = []
        if words:
            queries.append(" ".join(words[:6]))
            queries.extend(words[:6])
        if not queries and normalized:
            queries.append(normalized)
        deduped: list[str] = []
        for query in queries:
            cleaned = " ".join(query.split())
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped[:4]

    def _deterministic_catalog_grounding(
        self,
        session: Session,
        *,
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        inbound_text: str,
        run: AssistantRunModel,
    ) -> CatalogGrounding | None:
        if not self._needs_catalog_grounding(inbound_text):
            return None

        tool_names: list[str] = []
        search_result: dict[str, Any] | None = None
        selected_query = ""
        merged_items: dict[str, dict[str, Any]] = {}
        for query in self._catalog_search_queries(inbound_text):
            selected_query = query
            candidate_result = self._execute_and_record_tool(
                session,
                tool_name="search_catalog_variants",
                arguments={"query": query},
                channel=channel,
                conversation=conversation,
                run=run,
            )
            tool_names.append("search_catalog_variants")
            for item in candidate_result.get("items") or []:
                variant_id = str(item.get("variant_id") or "")
                if variant_id and variant_id not in merged_items:
                    merged_items[variant_id] = item
            if candidate_result.get("items") and search_result is None:
                search_result = candidate_result
            if len(candidate_result.get("items") or []) == 1 and self._is_exact_catalog_match(query, candidate_result["items"][0]):
                break

        if search_result is None:
            search_result = self._execute_and_record_tool(
                session,
                tool_name="search_catalog_variants",
                arguments={"query": ""},
                channel=channel,
                conversation=conversation,
                run=run,
            )
            tool_names.append("search_catalog_variants")
            for item in search_result.get("items") or []:
                variant_id = str(item.get("variant_id") or "")
                if variant_id and variant_id not in merged_items:
                    merged_items[variant_id] = item

        if merged_items:
            items = list(merged_items.values())
            selected = self._select_best_catalog_item(inbound_text, items)
            search_result = {**search_result, "items": [selected] if selected is not None else items[:8]}

        items = list(search_result.get("items") or [])
        price_intent, stock_intent, order_intent = self._catalog_intent_flags(inbound_text)
        availability_result = None
        price_result = None
        if len(items) == 1:
            variant_id = str(items[0].get("variant_id") or "").strip()
            if variant_id and (stock_intent or order_intent):
                availability_result = self._execute_and_record_tool(
                    session,
                    tool_name="get_variant_availability",
                    arguments={"variant_id": variant_id, "location_id": items[0].get("location_id") or ""},
                    channel=channel,
                    conversation=conversation,
                    run=run,
                )
                tool_names.append("get_variant_availability")
            if variant_id and price_intent:
                price_result = self._execute_and_record_tool(
                    session,
                    tool_name="get_variant_price",
                    arguments={"variant_id": variant_id},
                    channel=channel,
                    conversation=conversation,
                    run=run,
                )
                tool_names.append("get_variant_price")

        session.flush()
        return CatalogGrounding(
            query=selected_query,
            tool_names=tuple(tool_names),
            search_result=search_result,
            availability_result=availability_result,
            price_result=price_result,
        )

    def _is_exact_catalog_match(self, query: str, item: dict[str, Any]) -> bool:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return False
        sku = str(item.get("sku") or "").strip().lower()
        return bool(sku and normalized_query == sku)

    def _select_best_catalog_item(self, inbound_text: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        tokens = self._catalog_search_tokens(inbound_text)
        if not tokens or len(items) <= 1:
            return items[0] if len(items) == 1 else None
        scored = sorted(
            ((self._catalog_item_score(tokens, item), item) for item in items),
            key=lambda pair: pair[0],
            reverse=True,
        )
        top_score, top_item = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0
        if top_score >= 3 and top_score >= second_score + 1:
            return top_item
        return None

    def _catalog_search_tokens(self, text: str) -> list[str]:
        normalized = re.sub(r"[^a-z0-9+.#/-]+", " ", text.lower()).strip()
        return [
            word.strip("./-")
            for word in normalized.split()
            if word.strip("./-") and word.strip("./-") not in CATALOG_SEARCH_STOPWORDS
        ]

    def _catalog_item_score(self, tokens: list[str], item: dict[str, Any]) -> int:
        haystack = " ".join(
            str(item.get(field) or "")
            for field in ("label", "sku", "product_name", "brand", "category")
        ).lower()
        score = 0
        for token in tokens:
            if not token:
                continue
            if token == str(item.get("sku") or "").lower():
                score += 6
            elif token in haystack:
                score += 1
        return score

    def _catalog_grounding_message(self, grounding: CatalogGrounding) -> str:
        payload = {
            "query": grounding.query,
            "search": grounding.search_result,
            "availability": grounding.availability_result,
            "price": grounding.price_result,
        }
        return (
            "Fresh backend grounding results for this customer message. "
            "Use only these catalog, price, and availability facts if you answer product questions: "
            f"{json.dumps(_json_ready(payload))}"
        )

    def _compose_catalog_grounded_reply(
        self,
        *,
        client: ClientModel,
        playbook: AssistantPlaybookModel,
        inbound_text: str,
        grounding: CatalogGrounding,
    ) -> str:
        price_intent, stock_intent, order_intent = self._catalog_intent_flags(inbound_text)
        if not (price_intent or stock_intent or order_intent):
            return ""

        items = list(grounding.search_result.get("items") or [])
        health_prefix = ""
        if playbook.business_type == "pet_food" and self._has_risk_terms(inbound_text.lower()):
            health_prefix = "Because you mentioned a health concern, please check with a veterinarian before changing food. "

        if not items:
            query = grounding.query or "that item"
            return (
                f"{health_prefix}I checked the catalog for {query}, but I could not find a matching active item yet. "
                "Could you send the exact product name, size, flavor, or SKU so I can check again?"
            )

        if len(items) > 1:
            choices = "; ".join(self._catalog_choice_summary(item, client) for item in items[:3])
            return f"{health_prefix}I found a few matches: {choices}. Which one should I check or prepare for you?"

        variant = (grounding.availability_result or {}).get("variant") or items[0]
        price_variant = (grounding.price_result or {}).get("variant") or variant
        label = str(variant.get("label") or variant.get("product_name") or "that item")
        sku = str(variant.get("sku") or "").strip()
        sku_text = f" (SKU {sku})" if sku else ""

        facts: list[str] = []
        if stock_intent or order_intent:
            available = as_decimal(variant.get("available_to_sell") or ZERO)
            qty_text = self._format_quantity(available)
            if available > ZERO:
                facts.append(f"we have {qty_text} available")
            else:
                facts.append("it is not available right now")
        if price_intent:
            unit_price = price_variant.get("unit_price")
            if unit_price is not None:
                facts.append(f"the price is {self._format_money(unit_price, client)}")
            else:
                facts.append("I do not see a saved selling price for it yet")

        fact_text = ", and ".join(facts) if facts else "I found it in the catalog"
        next_step = "Would you like me to prepare a draft order for it?" if order_intent or stock_intent else "Would you like me to check anything else about it?"
        return f"{health_prefix}I checked {label}{sku_text}: {fact_text}. {next_step}"

    def _format_money(self, value: Any, client: ClientModel) -> str:
        amount = as_decimal(value).quantize(MONEY_QUANTUM)
        symbol = (client.currency_symbol or "").strip()
        code = (client.currency_code or "").strip().upper()
        if symbol:
            separator = " " if symbol[-1:].isalnum() else ""
            return f"{symbol}{separator}{amount}"
        return f"{amount} {code}".strip()

    def _format_quantity(self, value: Decimal) -> str:
        normalized = value.normalize()
        if normalized == normalized.to_integral():
            return str(int(normalized))
        return str(value.quantize(Decimal("0.001")).normalize())

    def _catalog_choice_summary(self, item: dict[str, Any], client: ClientModel) -> str:
        label = str(item.get("label") or item.get("product_name") or item.get("sku") or "item")
        sku = str(item.get("sku") or "").strip()
        available = as_decimal(item.get("available_to_sell") or ZERO)
        price = item.get("unit_price")
        parts = [label]
        if sku:
            parts.append(f"SKU {sku}")
        if price is not None:
            parts.append(self._format_money(price, client))
        parts.append(f"{self._format_quantity(available)} available" if available > ZERO else "not available")
        return f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]

    def _human_join(self, values: list[str]) -> str:
        if not values:
            return "a little more detail"
        if len(values) == 1:
            return values[0]
        return ", ".join(values[:-1]) + f", and {values[-1]}"

    def _tool_search_catalog(
        self,
        session: Session,
        client_id: str,
        arguments: dict[str, Any],
        channel: CustomerChannelModel,
    ) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        location_id = self._tool_location_id(session, client_id, str(arguments.get("location_id") or ""), channel)
        on_hand, reserved = self._stock_maps(session, client_id, location_id)
        pattern = f"%{query.lower()}%"
        stmt = (
            select(ProductModel, ProductVariantModel, SupplierModel, CategoryModel)
            .join(ProductVariantModel, ProductVariantModel.product_id == ProductModel.product_id)
            .outerjoin(SupplierModel, SupplierModel.supplier_id == ProductModel.supplier_id)
            .outerjoin(CategoryModel, CategoryModel.category_id == ProductModel.category_id)
            .where(
                ProductModel.client_id == client_id,
                ProductVariantModel.client_id == client_id,
                ProductModel.status == "active",
                ProductVariantModel.status == "active",
            )
            .order_by(ProductModel.name.asc(), ProductVariantModel.title.asc())
            .limit(8)
        )
        if query:
            stmt = stmt.where(
                or_(
                    func.lower(ProductModel.name).like(pattern),
                    func.lower(ProductVariantModel.title).like(pattern),
                    func.lower(ProductVariantModel.sku).like(pattern),
                    func.lower(ProductModel.brand).like(pattern),
                    func.lower(SupplierModel.name).like(pattern),
                    func.lower(CategoryModel.name).like(pattern),
                )
            )
        items = []
        for product, variant, supplier, category in session.execute(stmt).all():
            available = on_hand.get(str(variant.variant_id), ZERO) - reserved.get(str(variant.variant_id), ZERO)
            items.append(self._variant_tool_payload(product, variant, supplier, category, available, location_id))
        return {"ok": True, "location_id": location_id, "items": items}

    def _tool_variant_availability(
        self,
        session: Session,
        client_id: str,
        arguments: dict[str, Any],
        channel: CustomerChannelModel,
    ) -> dict[str, Any]:
        variant_id = str(arguments.get("variant_id", "")).strip()
        location_id = self._tool_location_id(session, client_id, str(arguments.get("location_id") or ""), channel)
        row = self._variant_row(session, client_id, variant_id)
        if row is None:
            return {"ok": False, "error": "Variant not found"}
        on_hand, reserved = self._stock_maps(session, client_id, location_id)
        product, variant, supplier, category = row
        available = on_hand.get(variant_id, ZERO) - reserved.get(variant_id, ZERO)
        return {
            "ok": True,
            "location_id": location_id,
            "variant": self._variant_tool_payload(product, variant, supplier, category, available, location_id),
        }

    def _tool_variant_price(self, session: Session, client_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        variant_id = str(arguments.get("variant_id", "")).strip()
        row = self._variant_row(session, client_id, variant_id)
        if row is None:
            return {"ok": False, "error": "Variant not found"}
        product, variant, supplier, category = row
        price = as_optional_decimal(variant.price_amount) if variant.price_amount is not None else as_optional_decimal(product.default_price_amount)
        min_price = as_optional_decimal(variant.min_price_amount) if variant.min_price_amount is not None else as_optional_decimal(product.min_price_amount)
        return {
            "ok": True,
            "variant": {
                "variant_id": str(variant.variant_id),
                "product_id": str(product.product_id),
                "product_name": product.name,
                "label": build_variant_label(product.name, variant.title),
                "sku": variant.sku,
                "brand": product.brand,
                "supplier": supplier.name if supplier else "",
                "category": category.name if category else "",
                "unit_price": price,
                "min_price": min_price,
            },
        }

    def _tool_recommendations(
        self,
        session: Session,
        client_id: str,
        arguments: dict[str, Any],
        channel: CustomerChannelModel,
    ) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        result = self._tool_search_catalog(session, client_id, {"query": query}, channel)
        recommendations = []
        for item in result["items"]:
            if as_decimal(item["available_to_sell"]) > ZERO:
                item["recommendation_reason"] = "Available now and matches the customer request."
                recommendations.append(item)
        return {"ok": True, "items": recommendations[:5]}

    def _tool_lookup_customer(
        self,
        session: Session,
        client_id: str,
        conversation: CustomerConversationModel,
    ) -> dict[str, Any]:
        filters = []
        phone = normalize_phone(conversation.external_sender_phone)
        email = normalize_email(conversation.external_sender_email)
        if phone:
            filters.append(CustomerModel.phone_normalized == phone)
        if email:
            filters.append(CustomerModel.email_normalized == email)
        if not filters:
            return {"ok": True, "customer": None, "message": "No phone or email is available yet."}
        customer = session.execute(
            select(CustomerModel).where(CustomerModel.client_id == client_id, or_(*filters))
        ).scalar_one_or_none()
        if customer is None:
            return {"ok": True, "customer": None}
        conversation.customer_id = customer.customer_id
        return {
            "ok": True,
            "customer": {
                "customer_id": str(customer.customer_id),
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
            },
        }

    def _tool_create_draft_order(
        self,
        session: Session,
        conversation: CustomerConversationModel,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        lines = list(arguments.get("lines") or [])
        if not lines:
            return {"ok": False, "error": "At least one line is required to create a draft order."}
        phone = str(arguments.get("customer_phone") or conversation.external_sender_phone or "").strip()
        email = str(arguments.get("customer_email") or conversation.external_sender_email or "").strip()
        if not normalize_phone(phone) and not normalize_email(email):
            return {"ok": False, "error": "Customer phone or email is required before creating a draft order."}
        customer_name = str(arguments.get("customer_name") or conversation.external_sender_name or "Customer").strip()
        assistant_user = AuthenticatedUser(
            user_id=None,  # type: ignore[arg-type]
            client_id=str(conversation.client_id),
            roles=["CLIENT_OWNER"],
            allowed_pages=["Sales"],
            email="assistant@easy-ecom.internal",
            name="AI Assistant",
            business_name=None,
        )
        order = self._sales.create_order(
            assistant_user,
            location_id=arguments.get("location_id") or None,
            customer_id=None,
            customer_payload={"name": customer_name, "phone": phone, "email": email, "address": ""},
            payment_status="unpaid",
            shipment_status="pending",
            notes=f"Draft created from AI conversation {conversation.conversation_id}. Staff must review before confirming.",
            lines=[
                {
                    "variant_id": str(line.get("variant_id")),
                    "quantity": as_decimal(line.get("quantity")),
                    "unit_price": None,
                    "discount_amount": ZERO,
                }
                for line in lines
            ],
            action="save_draft",
        )
        order_record = session.execute(
            select(SalesOrderModel).where(
                SalesOrderModel.client_id == conversation.client_id,
                SalesOrderModel.sales_order_id == order["sales_order_id"],
            )
        ).scalar_one_or_none()
        if order_record:
            order_record.source_type = "assistant"
        conversation.draft_order_id = order["sales_order_id"]
        return {
            "ok": True,
            "draft_order": {
                "sales_order_id": order["sales_order_id"],
                "order_number": order["order_number"],
                "status": order["status"],
                "total_amount": order["total_amount"],
            },
        }

    def _validate_response(
        self,
        *,
        inbound_text: str,
        response_text: str,
        tool_names: list[str],
        playbook: AssistantPlaybookModel,
    ) -> tuple[str, str]:
        lower = inbound_text.lower()
        response_lower = response_text.lower()
        grounded = bool(GROUNDING_TOOLS.intersection(tool_names))
        asks_clarifying_question = "?" in response_text and not re.search(r"\b(aed|usd|\$|available|in stock)\b", response_lower)
        if re.search(r"\b(price|cost|how much|available|availability|stock|in stock|do you have|order)\b", lower):
            if not grounded and not asks_clarifying_question:
                return "escalated", "Assistant attempted to answer a price, stock, or order question without tool grounding."
        if self._has_risk_terms(lower):
            if "request_human_escalation" in tool_names:
                return "escalated", "Assistant requested human escalation for a risky customer message."
            if self._has_escalation_risk_terms(lower):
                return "escalated", "Risky customer message needs human escalation."
            if playbook.business_type == "pet_food" and not re.search(r"\b(vet|veterinarian)\b", response_lower):
                return "escalated", "Pet health concern needs veterinarian-safe handling."
            if playbook.business_type == "electronics" and self._has_electronics_safety_terms(lower):
                return "escalated", "Electronics safety concern needs human escalation."
        if not response_text.strip():
            return "escalated", "Assistant produced an empty response."
        return "ok", ""

    def _system_prompt(self, client: ClientModel, playbook: AssistantPlaybookModel, channel: CustomerChannelModel) -> str:
        template = playbook.industry_template_json or INDUSTRY_TEMPLATES.get(playbook.business_type, INDUSTRY_TEMPLATES["general_retail"])
        policies = {**DEFAULT_POLICIES, **(playbook.policy_json or {})}
        sales_goals = playbook.sales_goals_json or {}
        escalation_rules = {**DEFAULT_ESCALATION_RULES, **(playbook.escalation_rules_json or {})}
        return "\n".join(
            [
                f"You are the customer service and sales assistant for {client.business_name}.",
                "Personality: natural, warm, concise, helpful, curious, and commercially sensible without pressure.",
                f"Brand personality: {playbook.brand_personality}. Channel: {channel.provider}.",
                "Conversation flow: understand intent, ask one useful clarifying question when needed, call tools for facts, answer clearly, then offer a next step.",
                "Use short natural transitions only when you are actually checking data with a tool.",
                "Never invent price, availability, discount, delivery, return, warranty, or product facts.",
                "For price or stock questions, call the relevant tool first. Availability is variant-level only.",
                "If the requested size, color, flavor, device model, or variant is unclear, ask a clarifying question instead of guessing.",
                "You may prepare a draft order only when the customer clearly wants to buy and enough customer contact data is available.",
                "Do not confirm orders, take payment, promise fulfillment, or mutate stock.",
                "Escalate politely for anger, disputes, medical/legal/safety questions, unavailable items without alternatives, or low confidence.",
                f"Business type: {playbook.business_type}. Ask about: {', '.join(template.get('questions', []))}.",
                f"Safety notes: {' '.join(template.get('safety', []))}",
                f"Tenant policies: {json.dumps(policies)}",
                f"Sales goals: {json.dumps(sales_goals)}",
                f"Escalation rules: {json.dumps(escalation_rules)}",
                f"Custom instructions: {playbook.custom_instructions}",
                f"Forbidden claims: {playbook.forbidden_claims}",
            ]
        )

    def _tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_catalog_variants",
                    "description": "Search active tenant catalog variants by product, variant title, SKU, brand, supplier, or category.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "location_id": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_variant_availability",
                    "description": "Get ledger-derived available stock for one variant at a tenant location.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "variant_id": {"type": "string"},
                            "location_id": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_variant_price",
                    "description": "Get default and minimum selling price for one variant.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "variant_id": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_product_recommendations",
                    "description": "Find available variants that match the customer's need and can be recommended.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "lookup_customer",
                    "description": "Look up a tenant customer by the current channel sender phone or email.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_draft_order",
                    "description": "Create a draft order for staff review. Never confirms, fulfills, reserves stock, or takes payment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {"type": "string"},
                            "customer_phone": {"type": "string"},
                            "customer_email": {"type": "string"},
                            "location_id": {"type": "string"},
                            "lines": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "variant_id": {"type": "string"},
                                        "quantity": {"type": "number"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "request_human_escalation",
                    "description": "Escalate the conversation to tenant staff when the situation is risky or uncertain.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"},
                        },
                    },
                },
            },
        ]

    def _parse_tool_arguments(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _conversation_history(self, session: Session, client_id: str, conversation_id: str) -> list[dict[str, str]]:
        rows = list(
            session.execute(
                select(CustomerMessageModel)
                .where(
                    CustomerMessageModel.client_id == client_id,
                    CustomerMessageModel.conversation_id == conversation_id,
                )
                .order_by(CustomerMessageModel.occurred_at.desc())
                .limit(8)
            ).scalars()
        )
        messages = []
        for message in reversed(rows):
            role = "assistant" if message.sender_role == "assistant" else "user"
            messages.append({"role": role, "content": message.message_text})
        return messages

    def _stock_maps(self, session: Session, client_id: str, location_id: str) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
        on_hand = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(InventoryLedgerModel.variant_id, func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), ZERO))
                .where(
                    InventoryLedgerModel.client_id == client_id,
                    InventoryLedgerModel.location_id == location_id,
                )
                .group_by(InventoryLedgerModel.variant_id)
            ).all()
        }
        reserved = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    SalesOrderItemModel.variant_id,
                    func.coalesce(
                        func.sum(
                            SalesOrderItemModel.quantity
                            - SalesOrderItemModel.quantity_fulfilled
                            - SalesOrderItemModel.quantity_cancelled
                        ),
                        ZERO,
                    ),
                )
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .where(
                    SalesOrderItemModel.client_id == client_id,
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.location_id == location_id,
                    SalesOrderModel.status == "confirmed",
                )
                .group_by(SalesOrderItemModel.variant_id)
            ).all()
        }
        return on_hand, reserved

    def _variant_row(self, session: Session, client_id: str, variant_id: str):
        return session.execute(
            select(ProductModel, ProductVariantModel, SupplierModel, CategoryModel)
            .join(ProductVariantModel, ProductVariantModel.product_id == ProductModel.product_id)
            .outerjoin(SupplierModel, SupplierModel.supplier_id == ProductModel.supplier_id)
            .outerjoin(CategoryModel, CategoryModel.category_id == ProductModel.category_id)
            .where(
                ProductModel.client_id == client_id,
                ProductVariantModel.client_id == client_id,
                ProductVariantModel.variant_id == variant_id,
                ProductModel.status == "active",
                ProductVariantModel.status == "active",
            )
        ).first()

    def _variant_tool_payload(
        self,
        product: ProductModel,
        variant: ProductVariantModel,
        supplier: SupplierModel | None,
        category: CategoryModel | None,
        available: Decimal,
        location_id: str,
    ) -> dict[str, Any]:
        price = as_optional_decimal(variant.price_amount) if variant.price_amount is not None else as_optional_decimal(product.default_price_amount)
        min_price = as_optional_decimal(variant.min_price_amount) if variant.min_price_amount is not None else as_optional_decimal(product.min_price_amount)
        return {
            "variant_id": str(variant.variant_id),
            "product_id": str(product.product_id),
            "product_name": product.name,
            "label": build_variant_label(product.name, variant.title),
            "sku": variant.sku,
            "brand": product.brand,
            "supplier": supplier.name if supplier else "",
            "category": category.name if category else "",
            "location_id": location_id,
            "unit_price": price,
            "min_price": min_price,
            "available_to_sell": available,
            "stock_status": "available" if available > ZERO else "unavailable",
        }

    def _tool_location_id(
        self,
        session: Session,
        client_id: str,
        requested_location_id: str,
        channel: CustomerChannelModel,
    ) -> str:
        if requested_location_id:
            location = session.execute(
                select(LocationModel).where(
                    LocationModel.client_id == client_id,
                    LocationModel.location_id == requested_location_id,
                    LocationModel.status == "active",
                )
            ).scalar_one_or_none()
            if location:
                return str(location.location_id)
        if channel.default_location_id:
            return str(channel.default_location_id)
        location = session.execute(
            select(LocationModel)
            .where(LocationModel.client_id == client_id, LocationModel.status == "active")
            .order_by(LocationModel.is_default.desc(), LocationModel.name.asc())
        ).scalars().first()
        if location is None:
            raise ApiException(status_code=400, code="LOCATION_REQUIRED", message="No active location is configured")
        return str(location.location_id)

    def _get_or_create_playbook(self, session: Session, client_id: str) -> AssistantPlaybookModel:
        playbook = session.execute(
            select(AssistantPlaybookModel).where(AssistantPlaybookModel.client_id == client_id)
        ).scalar_one_or_none()
        if playbook is not None:
            if not playbook.industry_template_json:
                playbook.industry_template_json = INDUSTRY_TEMPLATES.get(playbook.business_type, INDUSTRY_TEMPLATES["general_retail"])
            return playbook
        playbook = AssistantPlaybookModel(
            playbook_id=new_uuid(),
            client_id=client_id,
            business_type="general_retail",
            brand_personality="friendly",
            sales_goals_json={},
            policy_json=DEFAULT_POLICIES,
            escalation_rules_json=DEFAULT_ESCALATION_RULES,
            industry_template_json=INDUSTRY_TEMPLATES["general_retail"],
        )
        session.add(playbook)
        session.flush()
        return playbook

    def _get_or_create_conversation(
        self,
        session: Session,
        *,
        channel: CustomerChannelModel,
        external_sender_id: str,
        sender_name: str,
        sender_phone: str,
        sender_email: str,
    ) -> CustomerConversationModel:
        conversation = session.execute(
            select(CustomerConversationModel).where(
                CustomerConversationModel.client_id == channel.client_id,
                CustomerConversationModel.channel_id == channel.channel_id,
                CustomerConversationModel.external_sender_id == external_sender_id,
            )
        ).scalar_one_or_none()
        if conversation is not None:
            if sender_name and not conversation.external_sender_name:
                conversation.external_sender_name = sender_name
            if sender_phone and not conversation.external_sender_phone:
                conversation.external_sender_phone = sender_phone
            if sender_email and not conversation.external_sender_email:
                conversation.external_sender_email = sender_email
            return conversation
        conversation = CustomerConversationModel(
            conversation_id=new_uuid(),
            client_id=channel.client_id,
            channel_id=channel.channel_id,
            external_sender_id=external_sender_id,
            external_sender_name=sender_name.strip(),
            external_sender_phone=sender_phone.strip(),
            external_sender_email=sender_email.strip().lower(),
            status="open",
            memory_json={},
        )
        session.add(conversation)
        session.flush()
        return conversation

    def _create_message(
        self,
        session: Session,
        *,
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        direction: str,
        sender_role: str,
        message_text: str,
        provider_event_id: str,
        metadata: dict[str, Any],
        raw_payload: dict[str, Any] | None,
        outbound_status: str,
    ) -> CustomerMessageModel:
        message = CustomerMessageModel(
            message_id=new_uuid(),
            client_id=channel.client_id,
            conversation_id=conversation.conversation_id,
            channel_id=channel.channel_id,
            direction=direction,
            sender_role=sender_role,
            provider_event_id=provider_event_id.strip(),
            message_text=message_text.strip(),
            content_summary=_preview(message_text),
            outbound_status=outbound_status,
            raw_payload_json=raw_payload,
            metadata_json=metadata,
            occurred_at=now_utc(),
        )
        session.add(message)
        session.flush()
        return message

    def _conversation_rows(self, session: Session, client_id: str, *, limit: int):
        return list(
            session.execute(
                select(CustomerConversationModel, CustomerChannelModel)
                .join(CustomerChannelModel, CustomerChannelModel.channel_id == CustomerConversationModel.channel_id)
                .where(CustomerConversationModel.client_id == client_id, CustomerChannelModel.client_id == client_id)
                .order_by(CustomerConversationModel.last_message_at.desc().nullslast(), CustomerConversationModel.created_at.desc())
                .limit(limit)
            ).all()
        )

    def _get_conversation(self, session: Session, client_id: str, conversation_id: str) -> CustomerConversationModel:
        conversation = session.execute(
            select(CustomerConversationModel).where(
                CustomerConversationModel.client_id == client_id,
                CustomerConversationModel.conversation_id == conversation_id,
            )
        ).scalar_one_or_none()
        if conversation is None:
            raise ApiException(status_code=404, code="CONVERSATION_NOT_FOUND", message="Conversation not found")
        return conversation

    def _conversation_detail(self, session: Session, conversation: CustomerConversationModel) -> dict[str, Any]:
        channel = session.execute(
            select(CustomerChannelModel).where(
                CustomerChannelModel.client_id == conversation.client_id,
                CustomerChannelModel.channel_id == conversation.channel_id,
            )
        ).scalar_one()
        messages = list(
            session.execute(
                select(CustomerMessageModel)
                .where(
                    CustomerMessageModel.client_id == conversation.client_id,
                    CustomerMessageModel.conversation_id == conversation.conversation_id,
                )
                .order_by(CustomerMessageModel.occurred_at.asc())
                .limit(80)
            ).scalars()
        )
        runs = list(
            session.execute(
                select(AssistantRunModel)
                .where(
                    AssistantRunModel.client_id == conversation.client_id,
                    AssistantRunModel.conversation_id == conversation.conversation_id,
                )
                .order_by(AssistantRunModel.created_at.desc())
                .limit(10)
            ).scalars()
        )
        payload = self._conversation_summary_payload(conversation, channel)
        payload["memory"] = conversation.memory_json or {}
        payload["messages"] = [self._message_payload(message) for message in messages]
        payload["runs"] = [self._run_payload(session, run) for run in runs]
        return payload

    def _latest_outbound_for_inbound(self, session: Session, conversation: CustomerConversationModel) -> CustomerMessageModel | None:
        return session.execute(
            select(CustomerMessageModel)
            .where(
                CustomerMessageModel.client_id == conversation.client_id,
                CustomerMessageModel.conversation_id == conversation.conversation_id,
                CustomerMessageModel.direction == "outbound",
            )
            .order_by(CustomerMessageModel.occurred_at.desc())
        ).scalars().first()

    def _playbook_payload(self, playbook: AssistantPlaybookModel) -> dict[str, Any]:
        return {
            "playbook_id": str(playbook.playbook_id),
            "status": playbook.status,
            "business_type": playbook.business_type,
            "brand_personality": playbook.brand_personality,
            "custom_instructions": playbook.custom_instructions,
            "forbidden_claims": playbook.forbidden_claims,
            "sales_goals": playbook.sales_goals_json or {},
            "policies": {**DEFAULT_POLICIES, **(playbook.policy_json or {})},
            "escalation_rules": {**DEFAULT_ESCALATION_RULES, **(playbook.escalation_rules_json or {})},
            "industry_template": playbook.industry_template_json or {},
        }

    def _channel_payload(self, channel: CustomerChannelModel) -> dict[str, Any]:
        return {
            "channel_id": str(channel.channel_id),
            "provider": channel.provider,
            "display_name": channel.display_name,
            "status": channel.status,
            "external_account_id": channel.external_account_id,
            "webhook_key": channel.webhook_key,
            "default_location_id": str(channel.default_location_id) if channel.default_location_id else None,
            "auto_send_enabled": bool(channel.auto_send_enabled),
            "config": channel.config_json or {},
            "last_inbound_at": channel.last_inbound_at.isoformat() if channel.last_inbound_at else None,
            "last_outbound_at": channel.last_outbound_at.isoformat() if channel.last_outbound_at else None,
        }

    def _conversation_summary_payload(
        self,
        conversation: CustomerConversationModel,
        channel: CustomerChannelModel,
    ) -> dict[str, Any]:
        return {
            "conversation_id": str(conversation.conversation_id),
            "channel_id": str(channel.channel_id),
            "channel_provider": channel.provider,
            "channel_display_name": channel.display_name,
            "customer_id": str(conversation.customer_id) if conversation.customer_id else None,
            "draft_order_id": str(conversation.draft_order_id) if conversation.draft_order_id else None,
            "external_sender_id": conversation.external_sender_id,
            "external_sender_name": conversation.external_sender_name,
            "external_sender_phone": conversation.external_sender_phone,
            "external_sender_email": conversation.external_sender_email,
            "status": conversation.status,
            "latest_intent": conversation.latest_intent,
            "latest_summary": conversation.latest_summary,
            "escalation_reason": conversation.escalation_reason,
            "last_message_preview": conversation.last_message_preview,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        }

    def _message_payload(self, message: CustomerMessageModel) -> dict[str, Any]:
        return {
            "message_id": str(message.message_id),
            "conversation_id": str(message.conversation_id),
            "channel_id": str(message.channel_id),
            "direction": message.direction,
            "sender_role": message.sender_role,
            "provider_event_id": message.provider_event_id,
            "message_text": message.message_text,
            "outbound_status": message.outbound_status,
            "metadata": message.metadata_json or {},
            "occurred_at": message.occurred_at.isoformat() if message.occurred_at else None,
        }

    def _run_payload(self, session: Session, run: AssistantRunModel) -> dict[str, Any]:
        tool_calls = list(
            session.execute(
                select(AssistantToolCallModel)
                .where(AssistantToolCallModel.client_id == run.client_id, AssistantToolCallModel.run_id == run.run_id)
                .order_by(AssistantToolCallModel.created_at.asc())
            ).scalars()
        )
        return {
            "run_id": str(run.run_id),
            "conversation_id": str(run.conversation_id),
            "inbound_message_id": str(run.inbound_message_id),
            "status": run.status,
            "model_provider": run.model_provider,
            "model_name": run.model_name,
            "response_text": run.response_text,
            "validation_status": run.validation_status,
            "escalation_required": bool(run.escalation_required),
            "escalation_reason": run.escalation_reason,
            "total_tokens": run.total_tokens,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "tool_calls": [
                {
                    "tool_call_id": str(tool.tool_call_id),
                    "run_id": str(tool.run_id),
                    "tool_name": tool.tool_name,
                    "tool_arguments": tool.tool_arguments_json or {},
                    "tool_result": tool.tool_result_json or {},
                    "validation_status": tool.validation_status,
                    "created_at": tool.created_at.isoformat() if tool.created_at else None,
                }
                for tool in tool_calls
            ],
        }

    def _safe_escalation_text(self, business_name: str, inbound_text: str = "") -> str:
        lower = inbound_text.lower()
        if self._has_electronics_safety_terms(lower):
            return (
                f"Thanks for reaching out to {business_name}. Please stop using that device or charger now, unplug it if it is safe, "
                "and keep it away from heat or flammable items. I’m bringing a team member into this chat to help with the safest next step."
            )
        if re.search(r"\b(refund|complaint|angry)\b", lower):
            return (
                f"Thanks for reaching out to {business_name}. I’m bringing a team member into this chat so they can review the issue "
                "and help you with the right next step."
            )
        return (
            f"Thanks for reaching out to {business_name}. I want to make sure you get the right answer, "
            "so I’m bringing a team member into this chat to help with the details."
        )

    def _conversation_summary_text(self, previous: str, inbound: str, outbound: str) -> str:
        parts = [previous.strip(), f"Customer: {_preview(inbound, 120)}", f"Assistant: {_preview(outbound, 120)}"]
        return " | ".join(part for part in parts if part)[-1000:]

    def _has_risk_terms(self, text: str) -> bool:
        return bool(
            re.search(
                r"\b(angry|complaint|refund|lawsuit|legal|unsafe|sick|vomit|vomiting|diarrhea|allergy|allergic|sensitive|sensitivity|rash|burning|medicine|disease|pain|emergency|toxic|poison|smoke|overheat|overheating|shock|spark|swollen|battery)\b",
                text,
            )
        )

    def _has_escalation_risk_terms(self, text: str) -> bool:
        return bool(re.search(r"\b(angry|complaint|refund|lawsuit|legal|unsafe|emergency|toxic|poison)\b", text))

    def _has_allergy_terms(self, text: str) -> bool:
        return bool(re.search(r"\b(allergy|allergic|sensitive|sensitivity|rash|burning)\b", text))

    def _has_electronics_safety_terms(self, text: str) -> bool:
        return bool(re.search(r"\b(smoke|smoking|overheat|overheating|shock|spark|sparking|swollen|battery swelling|burning smell)\b", text))

    def _count(self, session: Session, model, client_id: str) -> int:
        return int(session.execute(select(func.count()).select_from(model).where(model.client_id == client_id)).scalar_one() or 0)

    def _count_where(self, session: Session, model, client_id: str, *conditions) -> int:
        return int(
            session.execute(select(func.count()).select_from(model).where(model.client_id == client_id, *conditions)).scalar_one()
            or 0
        )
