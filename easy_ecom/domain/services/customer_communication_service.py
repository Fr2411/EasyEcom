from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from copy import deepcopy
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
    "create_draft_order",
}

CATALOG_PRICE_RE = re.compile(r"\b(price|cost|how much|rate|unit price)\b")
CATALOG_STOCK_RE = re.compile(r"\b(available|availability|stock|in stock|do you have|do u have)\b")
CATALOG_ORDER_RE = re.compile(r"\b(order|buy|purchase|reserve|book it|take it)\b")
CATALOG_LOOKUP_RE = re.compile(r"\b(check|check if|look up|what about|compare|show me)\b")
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
            self._link_customer_from_contact(session, conversation)
            self._seed_memory_from_related(session, conversation)
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
        self._remember_inbound_context(
            conversation,
            playbook,
            inbound.message_text,
            metadata=inbound.metadata_json or {},
            raw_payload=inbound.raw_payload_json or {},
        )
        strategy_snapshot = self._conversation_strategy_snapshot(
            conversation,
            inbound.message_text,
            metadata=inbound.metadata_json or {},
            raw_payload=inbound.raw_payload_json or {},
        )
        self._apply_strategy_update(conversation, strategy_snapshot)
        memory_snapshot = self._memory_graph_snapshot(session, conversation, inbound_text=inbound.message_text)
        policy_reply = self._deterministic_policy_reply(playbook=playbook, inbound_text=inbound.message_text)
        if policy_reply:
            return policy_reply, tool_names, usage
        media_reply = self._media_context_reply(conversation=conversation, inbound_text=inbound.message_text)
        if media_reply:
            return media_reply, tool_names, usage
        negotiation_reply = self._negotiation_progress_reply(
            client=client,
            playbook=playbook,
            conversation=conversation,
            inbound_text=inbound.message_text,
        )
        if negotiation_reply:
            return negotiation_reply, tool_names, usage
        playbook_reply = self._deterministic_playbook_reply(
            client=client,
            playbook=playbook,
            inbound_text=inbound.message_text,
            memory=conversation.memory_json or {},
        )
        if playbook_reply:
            return playbook_reply, tool_names, usage
        sales_progress_reply = self._sales_progress_reply(
            client=client,
            conversation=conversation,
            inbound_text=inbound.message_text,
        )
        if sales_progress_reply:
            return sales_progress_reply, tool_names, usage
        recommendation_reply = self._deterministic_recommendation_reply(
            session,
            client=client,
            playbook=playbook,
            channel=channel,
            conversation=conversation,
            inbound_text=inbound.message_text,
            run=run,
        )
        if recommendation_reply is not None:
            final_text, recommendation_tools = recommendation_reply
            tool_names.extend(recommendation_tools)
            return final_text, tool_names, usage
        catalog_grounding = self._deterministic_catalog_grounding(
            session,
            channel=channel,
            conversation=conversation,
            inbound_text=inbound.message_text,
            run=run,
        )
        if catalog_grounding is not None:
            tool_names.extend(catalog_grounding.tool_names)
            draft_reply = self._deterministic_draft_order_reply(
                session,
                channel=channel,
                conversation=conversation,
                inbound=inbound,
                run=run,
                grounding=catalog_grounding,
            )
            if draft_reply is not None:
                final_text, draft_tools = draft_reply
                tool_names.extend(draft_tools)
                return final_text, tool_names, usage
            deterministic_reply = self._compose_catalog_grounded_reply(
                client=client,
                playbook=playbook,
                conversation=conversation,
                inbound_text=inbound.message_text,
                grounding=catalog_grounding,
            )
            if deterministic_reply:
                self._remember_catalog_grounding(conversation, catalog_grounding)
                return deterministic_reply, tool_names, usage

        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "system", "content": self._language_instruction(conversation)})
        messages.append({"role": "system", "content": self._strategy_message(strategy_snapshot)})
        messages.append({"role": "system", "content": self._memory_graph_message(memory_snapshot)})
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

    def _deterministic_playbook_reply(
        self,
        *,
        client: ClientModel,
        playbook: AssistantPlaybookModel,
        inbound_text: str,
        memory: dict[str, Any] | None = None,
    ) -> str:
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
        if (CATALOG_RECOMMENDATION_RE.search(lower) or self._has_shopping_discovery_intent(lower)) and not (price_intent or stock_intent):
            if memory and memory.get("pending_recommendation") and self._has_enough_recommendation_preferences(
                playbook, dict(memory.get("preferences") or {})
            ):
                return ""
            template = playbook.industry_template_json or INDUSTRY_TEMPLATES.get(playbook.business_type, INDUSTRY_TEMPLATES["general_retail"])
            questions = [str(question) for question in template.get("questions", []) if str(question).strip()]
            if playbook.business_type == "pet_food":
                return (
                    "I can help choose a suitable option. What pet is it for, and what are their age, breed or size, "
                    "current diet, allergies, and any health concerns?"
                )
            if playbook.business_type == "shoe_store":
                if memory and dict(memory.get("customer_signals") or {}).get("repeat_buyer"):
                    return (
                        "Absolutely — I can help with that again. Tell me the shoe size you want this time, whether it’s for running, work, casual wear, or something more formal, and any color, fit, or budget you want me to stay inside."
                    )
                return (
                    "Absolutely — I can help narrow that down. What shoe size do you need, and is it for running, work, casual wear, "
                    "formal use, or something else? If you already have a color, fit, or budget in mind, send that too."
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

    def _deterministic_policy_reply(self, *, playbook: AssistantPlaybookModel, inbound_text: str) -> str:
        price_intent, stock_intent, _ = self._catalog_intent_flags(inbound_text)
        if price_intent or stock_intent:
            return ""
        policy = self._policy_text_for_message(playbook, inbound_text)
        if not policy:
            return ""
        return f"Of course — here’s the store policy I can confirm right now: {policy}"

    def _deterministic_recommendation_reply(
        self,
        session: Session,
        *,
        client: ClientModel,
        playbook: AssistantPlaybookModel,
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        inbound_text: str,
        run: AssistantRunModel,
    ) -> tuple[str, list[str]] | None:
        memory = conversation.memory_json or {}
        pending_recommendation = bool(memory.get("pending_recommendation"))
        if not pending_recommendation or any(self._catalog_intent_flags(inbound_text)):
            return None
        preferences = dict(memory.get("preferences") or {})
        if not self._has_enough_recommendation_preferences(playbook, preferences):
            return None
        result = self._execute_and_record_tool(
            session,
            tool_name="search_catalog_variants",
            arguments={"query": ""},
            channel=channel,
            conversation=conversation,
            run=run,
        )
        items = [
            item
            for item in (result.get("items") or [])
            if as_decimal(item.get("available_to_sell") or ZERO) > ZERO
        ]
        ranked = sorted(
            ((self._recommendation_score(preferences, item), item) for item in items),
            key=lambda pair: pair[0],
            reverse=True,
        )
        choices = [item for score, item in ranked if score > 0][:3]
        if not choices:
            return None
        self._remember_catalog_choices(conversation, choices)
        pref_text = self._preference_summary(preferences)
        choice_lines = [
            f"{index}. {self._catalog_choice_summary(item, client)}"
            for index, item in enumerate(choices, start=1)
        ]
        prefix = self._continuity_prefix(conversation, warm=True)
        signals = dict(memory.get("customer_signals") or {})
        archetype = str(memory.get("buyer_archetype") or signals.get("buyer_archetype") or self._buyer_archetype(conversation, inbound_text))
        persuasion = self._persuasion_style(archetype)
        close_line = (
            "If one of these feels right, send the option number and I’ll move it forward for you."
            if signals.get("high_intent")
            else "Reply with the option number, or tell me what you want to change and I’ll narrow it further."
        )
        return (
            f"{prefix}based on {pref_text}, these look like the strongest matches right now:\n"
            + "\n".join(choice_lines)
            + f"\n{persuasion.get('recommendation_tail', '')} {close_line}".strip(),
            ["search_catalog_variants"],
        )

    def _deterministic_draft_order_reply(
        self,
        session: Session,
        *,
        channel: CustomerChannelModel,
        conversation: CustomerConversationModel,
        inbound: CustomerMessageModel,
        run: AssistantRunModel,
        grounding: CatalogGrounding,
    ) -> tuple[str, list[str]] | None:
        _, _, order_intent = self._catalog_intent_flags(inbound.message_text)
        if not order_intent:
            return None

        items = list(grounding.search_result.get("items") or [])
        if len(items) != 1:
            return None

        variant = (grounding.availability_result or {}).get("variant") or items[0]
        label = str(variant.get("label") or variant.get("product_name") or "that item")
        available = as_decimal(variant.get("available_to_sell") or ZERO)
        if available <= ZERO:
            self._update_sales_memory(conversation, focus_label=label, offer_state="out_of_stock", next_step="offer_alternative")
            return f"I checked {label}, and it’s out of stock right now. If you want, I can show you the closest available alternative so you don’t lose momentum.", []

        memory = self._memory(conversation)
        contact = dict(memory.get("customer_contact") or {})
        customer_name = (
            str(contact.get("name") or conversation.external_sender_name or "").strip()
            or self._extract_customer_name(inbound.message_text)
            or "Customer"
        )
        customer_phone = str(contact.get("phone") or conversation.external_sender_phone or self._extract_phone(inbound.message_text) or "").strip()
        customer_email = str(contact.get("email") or conversation.external_sender_email or self._extract_email(inbound.message_text) or "").strip()
        if not normalize_phone(customer_phone) and not normalize_email(customer_email):
            self._remember_catalog_grounding(conversation, grounding)
            self._update_sales_memory(conversation, focus_label=label, offer_state="contact_needed", next_step="collect_contact")
            return f"I can get a draft order ready for {label}. Just send a phone number or email and I’ll line it up for staff review.", []

        quantity = self._extract_quantity(inbound.message_text)
        quantity = max(Decimal("1"), min(quantity, available))
        result = self._execute_and_record_tool(
            session,
            tool_name="create_draft_order",
            arguments={
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_email": customer_email,
                "location_id": variant.get("location_id") or grounding.search_result.get("location_id") or "",
                "lines": [{"variant_id": str(variant.get("variant_id") or ""), "quantity": quantity}],
            },
            channel=channel,
            conversation=conversation,
            run=run,
        )
        if not result.get("ok"):
            return (
                f"I found {label}, but I could not prepare the draft order automatically. "
                "I’m bringing a team member in to review it and help you finish this.",
                ["create_draft_order"],
            )

        self._remember_catalog_grounding(conversation, grounding)
        memory = self._memory(conversation)
        memory["draft_order"] = _json_ready(result.get("draft_order") or {})
        conversation.memory_json = memory
        draft = result.get("draft_order") or {}
        self._update_sales_memory(
            conversation,
            focus_label=label,
            offer_state="draft_created",
            draft_order=draft,
            next_step="confirm_delivery_details",
        )
        draft = result.get("draft_order") or {}
        order_number = str(draft.get("order_number") or "the draft order")
        qty_text = self._format_quantity(quantity)
        return (
            f"Perfect — I’ve prepared draft order {order_number} for {qty_text} x {label}. "
            "The store team will review it before anything is confirmed, charged, or delivered. "
            "If you want, send delivery details and I’ll add them for the team so they can move faster.",
            ["create_draft_order"],
        )

    def _memory(self, conversation: CustomerConversationModel) -> dict[str, Any]:
        memory = conversation.memory_json if isinstance(conversation.memory_json, dict) else {}
        return dict(memory)

    def _link_customer_from_contact(self, session: Session, conversation: CustomerConversationModel) -> None:
        if conversation.customer_id:
            return
        filters = []
        normalized_phone = normalize_phone(conversation.external_sender_phone)
        normalized_email = normalize_email(conversation.external_sender_email)
        if normalized_phone:
            filters.append(CustomerModel.phone_normalized == normalized_phone)
        if normalized_email:
            filters.append(CustomerModel.email_normalized == normalized_email)
        if not filters:
            return
        customer = session.execute(
            select(CustomerModel).where(CustomerModel.client_id == conversation.client_id, or_(*filters))
        ).scalar_one_or_none()
        if customer is not None:
            conversation.customer_id = customer.customer_id

    def _related_conversations(
        self,
        session: Session,
        conversation: CustomerConversationModel,
        *,
        limit: int = 3,
    ) -> list[CustomerConversationModel]:
        stmt = (
            select(CustomerConversationModel)
            .where(
                CustomerConversationModel.client_id == conversation.client_id,
                CustomerConversationModel.conversation_id != conversation.conversation_id,
            )
            .order_by(CustomerConversationModel.last_message_at.desc().nullslast(), CustomerConversationModel.created_at.desc())
            .limit(12)
        )
        candidates = list(session.execute(stmt).scalars())
        normalized_phone = normalize_phone(conversation.external_sender_phone)
        normalized_email = normalize_email(conversation.external_sender_email)
        related: list[CustomerConversationModel] = []
        for candidate in candidates:
            same_customer = bool(conversation.customer_id and candidate.customer_id == conversation.customer_id)
            same_phone = bool(normalized_phone and normalize_phone(candidate.external_sender_phone) == normalized_phone)
            same_email = bool(normalized_email and normalize_email(candidate.external_sender_email) == normalized_email)
            if same_customer or same_phone or same_email:
                related.append(candidate)
            if len(related) >= limit:
                break
        return related

    def _merge_memory(self, base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base)
        for key, value in incoming.items():
            if value in (None, "", [], {}):
                continue
            current = merged.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                merged[key] = self._merge_memory(current, value)
            elif isinstance(current, list) and isinstance(value, list):
                merged[key] = value + [item for item in current if item not in value]
            else:
                merged[key] = deepcopy(value)
        return merged

    def _seed_memory_from_related(self, session: Session, conversation: CustomerConversationModel) -> None:
        memory = self._memory(conversation)
        if memory.get("graph_seeded"):
            return
        related = self._related_conversations(session, conversation)
        if not related:
            memory["graph_seeded"] = True
            conversation.memory_json = memory
            return
        latest = related[0]
        latest_memory = self._memory(latest)
        carry = {
            "preferences": latest_memory.get("preferences") or {},
            "customer_contact": latest_memory.get("customer_contact") or {},
            "last_variant": latest_memory.get("last_variant") or {},
            "recent_choices": latest_memory.get("recent_choices") or [],
            "sales_state": latest_memory.get("sales_state") or {},
            "customer_journey": latest_memory.get("customer_journey") or {},
            "thread_graph": {
                "related_conversations": [
                    {
                        "conversation_id": str(item.conversation_id),
                        "channel_id": str(item.channel_id),
                        "latest_intent": item.latest_intent,
                        "latest_summary": item.latest_summary,
                        "last_message_preview": item.last_message_preview,
                        "last_message_at": item.last_message_at.isoformat() if item.last_message_at else None,
                    }
                    for item in related[:3]
                ]
            },
        }
        memory = self._merge_memory(memory, carry)
        memory["graph_seeded"] = True
        memory.setdefault("thread_graph", {})
        memory["thread_graph"]["restored_from_conversation_id"] = str(latest.conversation_id)
        conversation.memory_json = _json_ready(memory)

    def _memory_graph_snapshot(
        self,
        session: Session,
        conversation: CustomerConversationModel,
        *,
        inbound_text: str,
    ) -> dict[str, Any]:
        memory = self._memory(conversation)
        related = self._related_conversations(session, conversation, limit=2)
        snapshot = {
            "customer_contact": memory.get("customer_contact") or {},
            "preferences": memory.get("preferences") or {},
            "last_variant": memory.get("last_variant") or {},
            "recent_choices": memory.get("recent_choices") or [],
            "sales_state": memory.get("sales_state") or {},
            "customer_journey": memory.get("customer_journey") or {},
            "conversation_status": conversation.status,
            "latest_intent": conversation.latest_intent,
            "latest_summary": conversation.latest_summary,
            "related_conversations": [
                {
                    "channel_id": str(item.channel_id),
                    "latest_intent": item.latest_intent,
                    "latest_summary": item.latest_summary,
                    "last_message_preview": item.last_message_preview,
                }
                for item in related
            ],
            "current_message_signals": {
                "asks_price": self._catalog_intent_flags(inbound_text)[0],
                "asks_stock": self._catalog_intent_flags(inbound_text)[1],
                "wants_to_order": self._catalog_intent_flags(inbound_text)[2],
            },
        }
        return _json_ready(snapshot)

    def _memory_graph_message(self, snapshot: dict[str, Any]) -> str:
        return (
            "Tenant-safe memory graph snapshot for this customer. Use it to continue naturally, avoid repeating questions, "
            "and keep selling context consistent. Treat it as tenant-local structured memory, not as permission to invent facts: "
            f"{json.dumps(snapshot)}"
        )

    def _update_sales_memory(
        self,
        conversation: CustomerConversationModel,
        *,
        focus_label: str = "",
        last_offered_price: Any | None = None,
        offer_state: str = "",
        draft_order: dict[str, Any] | None = None,
        next_step: str = "",
    ) -> None:
        memory = self._memory(conversation)
        sales_state = dict(memory.get("sales_state") or {})
        if focus_label:
            sales_state["focus_label"] = focus_label
        if last_offered_price is not None:
            sales_state["last_offered_price"] = _json_ready(last_offered_price)
        if offer_state:
            sales_state["offer_state"] = offer_state
        if draft_order:
            sales_state["draft_order"] = _json_ready(draft_order)
        if next_step:
            sales_state["next_step"] = next_step
        memory["sales_state"] = sales_state
        journey = dict(memory.get("customer_journey") or {})
        if focus_label:
            journey["current_focus"] = focus_label
        if offer_state:
            journey["stage"] = offer_state
        if next_step:
            journey["next_step"] = next_step
        memory["customer_journey"] = journey
        conversation.memory_json = _json_ready(memory)

    def _update_negotiation_memory(
        self,
        conversation: CustomerConversationModel,
        *,
        price_objection: bool = False,
        best_price_ask: bool = False,
        hesitation: bool = False,
        alternative_offered: bool = False,
        bundle_interest: bool = False,
        close_attempt: bool = False,
        last_move: str = "",
    ) -> None:
        memory = self._memory(conversation)
        state = dict(memory.get("negotiation_state") or {})
        if price_objection:
            state["price_objection_count"] = int(state.get("price_objection_count") or 0) + 1
        if best_price_ask:
            state["best_price_asked_count"] = int(state.get("best_price_asked_count") or 0) + 1
        if hesitation:
            state["stall_count"] = int(state.get("stall_count") or 0) + 1
        if alternative_offered:
            state["alternatives_offered_count"] = int(state.get("alternatives_offered_count") or 0) + 1
        if bundle_interest:
            state["bundle_interest_count"] = int(state.get("bundle_interest_count") or 0) + 1
        if close_attempt:
            state["close_attempt_count"] = int(state.get("close_attempt_count") or 0) + 1
        if last_move:
            state["last_move"] = last_move
        memory["negotiation_state"] = state
        conversation.memory_json = _json_ready(memory)

    def _remember_inbound_context(
        self,
        conversation: CustomerConversationModel,
        playbook: AssistantPlaybookModel,
        inbound_text: str,
        *,
        metadata: dict[str, Any] | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> None:
        memory = self._memory(conversation)
        preferences = dict(memory.get("preferences") or {})
        preferences.update(self._extract_customer_preferences(playbook, inbound_text))
        if preferences:
            memory["preferences"] = preferences

        contact = dict(memory.get("customer_contact") or {})
        name = self._extract_customer_name(inbound_text)
        phone = self._extract_phone(inbound_text)
        email = self._extract_email(inbound_text)
        if name:
            contact["name"] = name
            if not conversation.external_sender_name:
                conversation.external_sender_name = name
        if phone:
            contact["phone"] = phone
            if not conversation.external_sender_phone:
                conversation.external_sender_phone = phone
        if email:
            contact["email"] = email
            if not conversation.external_sender_email:
                conversation.external_sender_email = email
        if contact:
            memory["customer_contact"] = contact

        lead_context = self._extract_lead_context(inbound_text)
        if lead_context:
            memory["lead_context"] = {**dict(memory.get("lead_context") or {}), **lead_context}

        language_hint = self._detect_language_hint(inbound_text)
        if language_hint:
            memory["language_hint"] = language_hint

        modality = self._extract_message_modality(inbound_text, metadata, raw_payload)
        if modality.get("has_attachment"):
            memory["message_modality"] = modality

        if self._has_shopping_discovery_intent(inbound_text.lower()) or memory.get("pending_recommendation"):
            memory["pending_recommendation"] = True
        journey = dict(memory.get("customer_journey") or {})
        if preferences:
            journey["preference_summary"] = self._preference_summary(preferences)
        if contact:
            journey["contact_ready"] = bool(contact.get("phone") or contact.get("email"))
        if lead_context:
            journey["lead_source"] = lead_context.get("source") or lead_context.get("source_type") or ""
        if language_hint:
            journey["language"] = language_hint
        if modality.get("has_attachment"):
            journey["has_attachment"] = True
        if self._has_shopping_discovery_intent(inbound_text.lower()):
            journey["stage"] = "discovery"
            journey["next_step"] = "narrow_recommendation"
        memory["customer_journey"] = journey
        conversation.memory_json = memory

    def _remember_catalog_grounding(self, conversation: CustomerConversationModel, grounding: CatalogGrounding) -> None:
        items = list(grounding.search_result.get("items") or [])
        if len(items) != 1:
            return
        variant = dict((grounding.availability_result or {}).get("variant") or items[0])
        price_variant = (grounding.price_result or {}).get("variant") or {}
        if price_variant.get("unit_price") is not None:
            variant["unit_price"] = price_variant.get("unit_price")
        memory = self._memory(conversation)
        memory["last_variant"] = _json_ready(variant)
        memory["pending_recommendation"] = False
        conversation.memory_json = memory
        self._update_sales_memory(
            conversation,
            focus_label=str(variant.get("label") or variant.get("product_name") or ""),
            next_step="confirm_variant_or_order",
        )

    def _remember_catalog_choices(self, conversation: CustomerConversationModel, choices: list[dict[str, Any]]) -> None:
        memory = self._memory(conversation)
        memory["recent_choices"] = _json_ready([dict(choice) for choice in choices[:5]])
        memory["pending_recommendation"] = False
        conversation.memory_json = memory
        top_choice = choices[0] if choices else {}
        self._update_sales_memory(
            conversation,
            focus_label=str(top_choice.get("label") or top_choice.get("product_name") or ""),
            offer_state="recommendation_ready",
            next_step="customer_pick_option",
        )

    def _extract_customer_preferences(self, playbook: AssistantPlaybookModel, text: str) -> dict[str, Any]:
        lower = text.lower()
        preferences: dict[str, Any] = {}

        budget_match = re.search(
            r"\b(?:under|below|less than|max|maximum|budget(?: is)?|up to)\s*(?:aed|dh|dhs|usd|\$)?\s*([0-9]{2,6})\b",
            lower,
        ) or re.search(r"\b(?:aed|dh|dhs|usd|\$)\s*([0-9]{2,6})\b", lower)
        if budget_match:
            preferences["budget"] = budget_match.group(1)

        size_match = re.search(r"\b(?:size|sz)\s*([a-z]{1,3}|[0-9]{1,2})\b", lower)
        if not size_match and playbook.business_type in {"shoe_store", "fashion"}:
            size_match = re.search(r"\b(?:eu|uk|us)\s*([0-9]{1,2})\b", lower)
        if size_match:
            preferences["size"] = size_match.group(1).upper()

        color_terms = [
            "black",
            "white",
            "sand",
            "beige",
            "cream",
            "brown",
            "tan",
            "navy",
            "blue",
            "indigo",
            "grey",
            "gray",
            "charcoal",
            "green",
            "emerald",
            "red",
            "pink",
            "clear",
            "neutral",
        ]
        colors = [color for color in color_terms if re.search(rf"\b{re.escape(color)}s?\b", lower)]
        if "not too flashy" in lower or "nothing flashy" in lower:
            colors.append("neutral")
            preferences["style"] = "not too flashy"
        if colors:
            preferences["colors"] = sorted(set(colors))

        if re.search(r"\boffice party\b", lower):
            preferences["occasion"] = "office party"
        elif re.search(r"\b(work|office|formal|casual|running|gym|breakfast|gift|travel)\b", lower):
            preferences["occasion"] = re.search(r"\b(work|office|formal|casual|running|gym|breakfast|gift|travel)\b", lower).group(1)

        if playbook.business_type == "pet_food":
            pet_match = re.search(r"\b(dog|puppy|cat|kitten|bird|rabbit)\b", lower)
            if pet_match:
                preferences["pet_type"] = pet_match.group(1)
            if self._has_allergy_terms(lower):
                preferences["allergy_concern"] = True
        if playbook.business_type == "electronics":
            model_match = re.search(r"\b(iphone|ipad|samsung|galaxy|macbook|laptop|usb-c|type-c|android)\b", lower)
            if model_match:
                preferences["device_or_model"] = model_match.group(1)
        if playbook.business_type == "cosmetics":
            skin_match = re.search(r"\b(oily|dry|combination|sensitive|acne|dull|hydration|brightening)\b", lower)
            if skin_match:
                preferences["skin_need"] = skin_match.group(1)

        return preferences

    def _extract_customer_name(self, text: str) -> str:
        match = re.search(r"\bmy name is\s+([A-Za-z][A-Za-z .'-]{1,80})", text, re.IGNORECASE)
        if not match:
            return ""
        name = re.split(r"\b(?:phone|mobile|email|and|,)\b", match.group(1).strip(), maxsplit=1, flags=re.IGNORECASE)[0]
        return " ".join(name.split()).strip(" .,'-")

    def _extract_phone(self, text: str) -> str:
        match = re.search(r"(?<!\w)(\+?\d[\d\s().-]{6,}\d)(?!\w)", text)
        if not match:
            return ""
        return " ".join(match.group(1).split())

    def _extract_email(self, text: str) -> str:
        match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.IGNORECASE)
        return match.group(0).lower() if match else ""

    def _extract_quantity(self, text: str) -> Decimal:
        lower = text.lower()
        match = re.search(r"\b(?:qty|quantity|take|need|want|buy|order)\s+([0-9]{1,3})\b", lower)
        if not match:
            return Decimal("1")
        return as_decimal(match.group(1))

    def _extract_lead_context(self, text: str) -> dict[str, Any]:
        lower = text.lower()
        source = ""
        if re.search(r"\binstagram|insta|ig|reel|story\b", lower):
            source = "instagram"
        elif re.search(r"\bfacebook|fb\b", lower):
            source = "facebook"
        elif re.search(r"\btiktok\b", lower):
            source = "tiktok"
        elif re.search(r"\bgoogle\b", lower):
            source = "google"
        elif re.search(r"\bwebsite\b", lower):
            source = "website"
        elif re.search(r"\bwhatsapp\b", lower):
            source = "whatsapp"

        source_type = ""
        if re.search(r"\b(ad|ads|campaign|promo|promotion|sponsored)\b", lower):
            source_type = "campaign"
        elif re.search(r"\b(post|reel|story|video)\b", lower):
            source_type = "content"
        elif re.search(r"\b(referred|referral|friend told me|someone told me|recommended by)\b", lower):
            source_type = "referral"
        elif source:
            source_type = "organic"

        if not source and not source_type:
            return {}
        return {"source": source, "source_type": source_type}

    def _detect_language_hint(self, text: str) -> str:
        if re.search(r"[\u0600-\u06FF]", text):
            return "arabic"
        if re.search(r"[\u0980-\u09FF]", text):
            return "bengali"
        if re.search(r"[\u0900-\u097F]", text):
            return "hindi"
        latin_letters = re.findall(r"[A-Za-z]", text)
        if latin_letters:
            return "english"
        return ""

    def _extract_message_modality(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        lower = text.lower()
        metadata = metadata or {}
        raw_payload = raw_payload or {}
        attachments = metadata.get("attachments") or raw_payload.get("attachments") or []
        has_attachment = bool(attachments or metadata.get("attachment") or raw_payload.get("attachment"))
        has_image = has_attachment and any("image" in str(item).lower() for item in attachments) if isinstance(attachments, list) else has_attachment
        mentions_image = bool(re.search(r"\b(image|photo|pic|picture|screenshot|screen shot|attached)\b", lower))
        if mentions_image and not has_attachment:
            has_image = True
        return {
            "has_attachment": bool(has_attachment or mentions_image),
            "has_image": bool(has_image or mentions_image),
        }

    def _has_shopping_discovery_intent(self, lower_text: str) -> bool:
        return bool(
            re.search(
                r"\b(looking for|need something|need help|help me choose|recommend|suggest|which|what should i buy|best|suitable)\b",
                lower_text,
            )
        )

    def _has_enough_recommendation_preferences(self, playbook: AssistantPlaybookModel, preferences: dict[str, Any]) -> bool:
        if playbook.business_type in {"fashion", "shoe_store"}:
            return bool(preferences.get("size") and (preferences.get("colors") or preferences.get("occasion") or preferences.get("budget")))
        if playbook.business_type == "pet_food":
            return bool(preferences.get("pet_type") and not preferences.get("allergy_concern"))
        if playbook.business_type == "electronics":
            return bool(preferences.get("device_or_model") or preferences.get("budget"))
        if playbook.business_type == "cosmetics":
            return bool(preferences.get("skin_need"))
        return bool(preferences)

    def _recommendation_score(self, preferences: dict[str, Any], item: dict[str, Any]) -> int:
        haystack = " ".join(
            str(item.get(field) or "")
            for field in ("label", "sku", "product_name", "brand", "category")
        ).lower()
        score = 0
        size = str(preferences.get("size") or "").lower()
        if size and re.search(rf"\b{re.escape(size)}\b", haystack):
            score += 5
        colors = [str(color).lower() for color in preferences.get("colors") or []]
        if "neutral" in colors:
            neutral_terms = ["sand", "beige", "cream", "tan", "black", "white", "navy", "grey", "gray", "charcoal"]
            if any(term in haystack for term in neutral_terms):
                score += 3
        score += sum(3 for color in colors if color != "neutral" and color in haystack)
        occasion = str(preferences.get("occasion") or "").lower()
        if occasion:
            occasion_terms = {
                "office party": ["blazer", "dress", "shirt", "trouser", "loafer"],
                "office": ["blazer", "shirt", "trouser", "loafer"],
                "work": ["blazer", "shirt", "trouser", "loafer", "sneaker"],
                "running": ["run", "running", "trainer"],
                "breakfast": ["oats", "coffee", "bread", "honey"],
            }
            score += sum(2 for term in occasion_terms.get(occasion, [occasion]) if term in haystack)
        budget = preferences.get("budget")
        if budget and item.get("unit_price") is not None:
            price = as_decimal(item.get("unit_price"))
            budget_amount = as_decimal(budget)
            if price <= budget_amount:
                score += 4
            elif price <= budget_amount * Decimal("1.15"):
                score += 1
            else:
                score -= 4
        if as_decimal(item.get("available_to_sell") or ZERO) > ZERO:
            score += 1
        return score

    def _preference_summary(self, preferences: dict[str, Any]) -> str:
        parts: list[str] = []
        if preferences.get("size"):
            parts.append(f"size {preferences['size']}")
        if preferences.get("colors"):
            parts.append(f"{self._human_join([str(color) for color in preferences['colors']])} colors")
        if preferences.get("occasion"):
            parts.append(str(preferences["occasion"]))
        if preferences.get("budget"):
            parts.append(f"budget around {preferences['budget']}")
        return self._human_join(parts) if parts else "what you shared"

    def _continuity_prefix(self, conversation: CustomerConversationModel, *, warm: bool = False) -> str:
        memory = self._memory(conversation)
        journey = dict(memory.get("customer_journey") or {})
        restored = dict(memory.get("thread_graph") or {}).get("restored_from_conversation_id")
        focus = str(journey.get("current_focus") or memory.get("sales_state", {}).get("focus_label") or "").strip()
        if restored and focus:
            return f"Picking up from where we left off with {focus}, " if warm else f"About {focus}, "
        if restored:
            return "Picking up from where we left off, " if warm else "From earlier, "
        if focus:
            return f"On {focus}, " if warm else ""
        return ""

    def _numbered_options(self, items: list[str]) -> str:
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))

    def _buyer_archetype(self, conversation: CustomerConversationModel, inbound_text: str) -> str:
        memory = self._memory(conversation)
        stored = str(memory.get("buyer_archetype") or "").strip()
        if stored:
            return stored
        lower = inbound_text.lower()
        preferences = dict(memory.get("preferences") or {})
        lead_context = dict(memory.get("lead_context") or {})
        if conversation.customer_id or dict(memory.get("thread_graph") or {}).get("restored_from_conversation_id"):
            return "repeat_buyer"
        if re.search(r"\b(cheap|cheaper|budget|discount|best price|lower|offer)\b", lower) or preferences.get("budget"):
            return "budget_buyer"
        if re.search(r"\b(urgent|quick|fast|asap|today|immediately|right now)\b", lower):
            return "convenience_buyer"
        if lead_context.get("source_type") == "campaign":
            return "campaign_buyer"
        if re.search(r"\b(best|premium|top|quality|comfortable|long lasting|leather)\b", lower):
            return "premium_buyer"
        return "explorer"

    def _persuasion_style(self, archetype: str) -> dict[str, str]:
        styles = {
            "repeat_buyer": {
                "closing": "make the next step feel easy because trust already exists",
                "recommendation_tail": "I can keep this fast for you.",
                "comparison_tail": "I’d keep it simple and go with the option that needs the least rethinking.",
            },
            "budget_buyer": {
                "closing": "protect margin but help the customer feel smart about value",
                "recommendation_tail": "I’ve kept value for money in mind here.",
                "comparison_tail": "I’d lean toward the one that gives the cleaner value-for-money choice.",
            },
            "convenience_buyer": {
                "closing": "reduce friction and move quickly",
                "recommendation_tail": "I’m keeping this tight so you can decide quickly.",
                "comparison_tail": "I’d lean toward the easier choice so you can move on quickly.",
            },
            "campaign_buyer": {
                "closing": "keep momentum from ad or content traffic and avoid long back-and-forth",
                "recommendation_tail": "I’m keeping this simple so you can decide quickly from what brought you in.",
                "comparison_tail": "I’d lean toward the clearest fit so the decision stays easy.",
            },
            "premium_buyer": {
                "closing": "justify the stronger option with confidence and reassurance",
                "recommendation_tail": "I’ve leaned toward the stronger-quality picks here.",
                "comparison_tail": "I’d lean toward the stronger overall option, not just the cheaper one.",
            },
            "explorer": {
                "closing": "guide without pressure",
                "recommendation_tail": "I can narrow it further once you react to these.",
                "comparison_tail": "I’d lean toward the safer overall fit based on what you’ve shared.",
            },
        }
        return styles.get(archetype, styles["explorer"])

    def _language_instruction(self, conversation: CustomerConversationModel) -> str:
        language_hint = str(self._memory(conversation).get("language_hint") or "").strip().lower()
        labels = {
            "arabic": "Reply in Arabic unless the customer switches language.",
            "bengali": "Reply in Bengali unless the customer switches language.",
            "hindi": "Reply in Hindi unless the customer switches language.",
            "english": "Reply in natural English unless the customer switches language.",
        }
        return labels.get(language_hint, "Reply in the customer's clearest language.")

    def _extract_customer_signals(
        self,
        conversation: CustomerConversationModel,
        inbound_text: str,
    ) -> dict[str, Any]:
        lower = inbound_text.lower()
        memory = self._memory(conversation)
        sales_state = dict(memory.get("sales_state") or {})
        customer_contact = dict(memory.get("customer_contact") or {})
        lead_context = dict(memory.get("lead_context") or {})
        buyer_archetype = self._buyer_archetype(conversation, inbound_text)
        return {
            "price_sensitive": bool(re.search(r"\b(cheap|cheaper|budget|discount|best price|lower|offer|expensive|too much|too high)\b", lower)),
            "hesitant": bool(re.search(r"\b(later|think about it|let me think|maybe later|not sure|i'll come back)\b", lower)),
            "high_intent": bool(self._catalog_intent_flags(inbound_text)[2] or sales_state.get("draft_order") or re.search(r"\b(take it|book it|let's do it|prepare it|i want this)\b", lower)),
            "repeat_buyer": bool(conversation.customer_id or dict(memory.get("thread_graph") or {}).get("restored_from_conversation_id")),
            "contact_ready": bool(customer_contact.get("phone") or customer_contact.get("email") or conversation.external_sender_phone or conversation.external_sender_email),
            "campaign_origin": bool(lead_context.get("source_type") == "campaign"),
            "referral_origin": bool(lead_context.get("source_type") == "referral"),
            "buyer_archetype": buyer_archetype,
        }

    def _conversation_strategy_snapshot(
        self,
        conversation: CustomerConversationModel,
        inbound_text: str,
        *,
        metadata: dict[str, Any] | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        memory = self._memory(conversation)
        journey = dict(memory.get("customer_journey") or {})
        sales_state = dict(memory.get("sales_state") or {})
        negotiation_state = dict(memory.get("negotiation_state") or {})
        lead_context = dict(memory.get("lead_context") or {})
        language_hint = str(memory.get("language_hint") or self._detect_language_hint(inbound_text) or "")
        message_modality = self._extract_message_modality(inbound_text, metadata, raw_payload)
        signals = self._extract_customer_signals(conversation, inbound_text)
        buyer_archetype = str(signals.get("buyer_archetype") or self._buyer_archetype(conversation, inbound_text))
        persuasion = self._persuasion_style(buyer_archetype)
        lower = inbound_text.lower()
        price_intent, stock_intent, order_intent = self._catalog_intent_flags(inbound_text)
        if self._has_escalation_risk_terms(lower):
            stage = "support"
        elif order_intent or sales_state.get("offer_state") in {"draft_created", "contact_needed"}:
            stage = "closing"
        elif signals["price_sensitive"] or sales_state.get("last_offered_price"):
            stage = "negotiation"
        elif journey.get("stage") == "discovery" and sales_state.get("focus_label"):
            stage = "comparison"
        elif self._has_shopping_discovery_intent(lower):
            stage = "discovery"
        elif price_intent or stock_intent or sales_state.get("focus_label"):
            stage = "consideration"
        else:
            stage = str(journey.get("stage") or "discovery")

        if stage == "support":
            next_best_action = "handoff_to_human"
        elif stage == "closing" and not signals["contact_ready"]:
            next_best_action = "collect_contact_and_prepare_draft"
        elif stage == "closing":
            next_best_action = "prepare_or_advance_order"
        elif stage == "negotiation" and sales_state.get("focus_label"):
            if int(negotiation_state.get("stall_count") or 0) >= 2:
                next_best_action = "reduce_pressure_and_hold_context"
            elif int(negotiation_state.get("price_objection_count") or 0) >= 2 and int(negotiation_state.get("alternatives_offered_count") or 0) == 0:
                next_best_action = "offer_alternative_then_close"
            elif int(negotiation_state.get("best_price_asked_count") or 0) >= 2:
                next_best_action = "restate_policy_then_close"
            else:
                next_best_action = "handle_price_objection_and_soft_close"
        elif stage == "comparison" and sales_state.get("focus_label"):
            next_best_action = "compare_and_reduce_choice"
        elif stage == "consideration" and stock_intent and price_intent:
            next_best_action = "answer_facts_then_soft_close"
        elif stage == "consideration":
            next_best_action = "answer_facts_and_offer_next_step"
        else:
            next_best_action = "narrow_need_with_one_question"

        return {
            "journey_stage": stage,
            "customer_signals": signals,
            "lead_context": lead_context,
            "language_hint": language_hint,
            "message_modality": message_modality,
            "negotiation_state": negotiation_state,
            "buyer_archetype": buyer_archetype,
            "persuasion_style": persuasion,
            "commercial_goal": {
                "discovery": "move_from_need_to_shortlist",
                "comparison": "reduce_choice_friction",
                "consideration": "build_confidence_and_keep_momentum",
                "negotiation": "protect_margin_and_close",
                "closing": "convert_to_draft_order",
                "support": "preserve_trust_and_handoff",
            }.get(stage, "move_conversation_forward"),
            "next_best_action": next_best_action,
            "current_focus": sales_state.get("focus_label") or journey.get("current_focus") or "",
        }

    def _strategy_message(self, snapshot: dict[str, Any]) -> str:
        return (
            "Conversation strategy snapshot. Use it to decide the most commercially useful next move instead of replying only to the last sentence. "
            "Customers may be random, may switch topics, may arrive from ads or referrals, and may use different languages. "
            "Match the customer's language when it is clear, do not force a rigid script, and steer the conversation forward with one smart next step: "
            f"{json.dumps(_json_ready(snapshot))}"
        )

    def _apply_strategy_update(self, conversation: CustomerConversationModel, snapshot: dict[str, Any]) -> None:
        memory = self._memory(conversation)
        journey = dict(memory.get("customer_journey") or {})
        journey["stage"] = snapshot.get("journey_stage")
        journey["next_best_action"] = snapshot.get("next_best_action")
        journey["commercial_goal"] = snapshot.get("commercial_goal")
        if snapshot.get("current_focus"):
            journey["current_focus"] = snapshot.get("current_focus")
        memory["customer_journey"] = journey
        memory["customer_signals"] = snapshot.get("customer_signals") or {}
        if snapshot.get("lead_context"):
            memory["lead_context"] = snapshot.get("lead_context") or {}
        if snapshot.get("buyer_archetype"):
            memory["buyer_archetype"] = snapshot.get("buyer_archetype")
        if snapshot.get("persuasion_style"):
            memory["persuasion_style"] = snapshot.get("persuasion_style") or {}
        if snapshot.get("language_hint"):
            memory["language_hint"] = snapshot.get("language_hint")
        if snapshot.get("message_modality"):
            memory["message_modality"] = snapshot.get("message_modality") or {}
        if snapshot.get("negotiation_state"):
            memory["negotiation_state"] = snapshot.get("negotiation_state") or {}
        conversation.memory_json = _json_ready(memory)
        conversation.latest_intent = str(snapshot.get("journey_stage") or "")

    def _negotiation_progress_reply(
        self,
        *,
        client: ClientModel,
        playbook: AssistantPlaybookModel,
        conversation: CustomerConversationModel,
        inbound_text: str,
    ) -> str:
        memory = self._memory(conversation)
        lower = inbound_text.lower()
        sales_state = dict(memory.get("sales_state") or {})
        negotiation_state = dict(memory.get("negotiation_state") or {})
        focus_label = str(sales_state.get("focus_label") or memory.get("last_variant", {}).get("label") or "").strip()
        if not focus_label:
            return ""

        archetype = str(memory.get("buyer_archetype") or self._buyer_archetype(conversation, inbound_text))
        last_offered_price = sales_state.get("last_offered_price")
        price_text = self._format_money(last_offered_price, client) if last_offered_price not in {None, ""} else ""
        discounts_policy = str(({**DEFAULT_POLICIES, **(playbook.policy_json or {})}.get("discounts") or "")).strip()
        cross_sell_enabled = bool((playbook.sales_goals_json or {}).get("cross_sell"))

        asks_best_price = bool(re.search(r"\b(best price|last price|final price|best you can do|your best|lowest|do better|better price)\b", lower))
        says_expensive = bool(re.search(r"\b(expensive|too much|too high|pricey|costly)\b", lower))
        asks_bundle = bool(re.search(r"\b(bundle|care kit|laces|socks|accessories|anything to go with it|match with it)\b", lower))
        urgency = bool(re.search(r"\b(today|now|right away|asap|quickly)\b", lower))
        repeated_price_push = int(negotiation_state.get("best_price_asked_count") or 0) >= 1
        stalled = int(negotiation_state.get("stall_count") or 0) >= 2

        if asks_best_price and price_text:
            self._update_negotiation_memory(conversation, best_price_ask=True, close_attempt=True, last_move="price_policy_close")
            if discounts_policy and repeated_price_push:
                return (
                    f"For {focus_label}, the current price I can confirm is {price_text}. {discounts_policy} "
                    "I don’t want to drag you in circles, so the best next move is either the closest lower-price alternative or a draft order for staff review if you want this one."
                )
            if discounts_policy:
                if archetype in {"repeat_buyer", "campaign_buyer"}:
                    return (
                        f"On {focus_label}, the current stored price I can confirm is {price_text}. {discounts_policy} "
                        "If you want, I can keep this moving by checking the closest lower-price alternative or lining up the draft order for staff review."
                    )
                return (
                    f"For {focus_label}, the current price I can confirm is {price_text}. {discounts_policy} "
                    "If price is the main decision point, I can also show the closest lower-price alternative or keep this one moving for you."
                )
            return (
                f"For {focus_label}, the current price I can confirm is {price_text}. "
                "If you want, I can either compare it with the closest lower-price alternative or move it forward for staff review."
            )

        if says_expensive:
            self._update_negotiation_memory(conversation, price_objection=True, alternative_offered=True, last_move="offer_lower_price_alternative")
            if archetype == "premium_buyer":
                return (
                    f"I understand. On {focus_label}, you’d mainly be paying for the stronger overall option rather than the lowest price. "
                    "If you want, I can compare it with the nearest cheaper alternative so you can decide whether the step-up is worth it."
                )
            return (
                f"I understand. If {focus_label} feels a bit high, I can quickly show you the closest lower-price alternative so you can compare value side by side."
            )

        if asks_bundle and cross_sell_enabled:
            self._update_negotiation_memory(conversation, bundle_interest=True, last_move="bundle_interest")
            bundle_hint = "matching care items or accessories"
            if playbook.business_type == "shoe_store":
                bundle_hint = "matching socks, care items, or insoles"
            return (
                f"I can help with that around {focus_label}. If you want, I can also look for {bundle_hint} that make sense with it, "
                "and I’ll keep it practical rather than piling on extras."
            )

        if urgency and self._catalog_intent_flags(inbound_text)[2]:
            self._update_negotiation_memory(conversation, close_attempt=True, last_move="urgent_close")
            return (
                f"Yes — I can keep {focus_label} moving quickly. Send a phone number or email if I don’t have it yet, and I’ll line up the draft order for staff review."
            )

        if stalled:
            return (
                f"No pressure — I’ll keep {focus_label} in context for you. When you’re ready, I can either pick back up with the same option, compare one alternative, or move straight to the draft order."
            )

        return ""

    def _media_context_reply(
        self,
        *,
        conversation: CustomerConversationModel,
        inbound_text: str,
    ) -> str:
        memory = self._memory(conversation)
        modality = dict(memory.get("message_modality") or {})
        if not modality.get("has_image"):
            return ""
        if self._catalog_intent_flags(inbound_text)[0] or self._catalog_intent_flags(inbound_text)[1]:
            return ""
        return (
            "I can help with that. If you’re referring to an image or screenshot, tell me the product name, size, color, SKU, "
            "or the exact issue you want me to focus on, and I’ll take it from there."
        )

    def _sales_progress_reply(
        self,
        *,
        client: ClientModel,
        conversation: CustomerConversationModel,
        inbound_text: str,
    ) -> str:
        memory = self._memory(conversation)
        lower = inbound_text.lower()
        recent_choices = [dict(item) for item in (memory.get("recent_choices") or []) if isinstance(item, dict)]
        preferences = dict(memory.get("preferences") or {})
        lead_context = dict(memory.get("lead_context") or {})
        focus_variant = dict(memory.get("last_variant") or {})
        focus_label = str((memory.get("sales_state") or {}).get("focus_label") or focus_variant.get("label") or "").strip()
        prefix = self._continuity_prefix(conversation, warm=True)
        archetype = str(memory.get("buyer_archetype") or self._buyer_archetype(conversation, inbound_text))
        persuasion = self._persuasion_style(archetype)

        if re.search(r"\b(which one|which is better|better one|difference|compare|vs\.?|versus)\b", lower) and len(recent_choices) >= 2:
            first, second = recent_choices[0], recent_choices[1]
            first_label = str(first.get("label") or first.get("product_name") or "Option 1")
            second_label = str(second.get("label") or second.get("product_name") or "Option 2")
            first_price = self._format_money(first.get("unit_price"), client) if first.get("unit_price") is not None else ""
            second_price = self._format_money(second.get("unit_price"), client) if second.get("unit_price") is not None else ""
            budget = as_decimal(preferences.get("budget") or ZERO)
            first_amount = as_decimal(first.get("unit_price") or ZERO)
            second_amount = as_decimal(second.get("unit_price") or ZERO)
            if budget > ZERO and second_amount > ZERO and first_amount > ZERO:
                preferred = first if abs(first_amount - budget) <= abs(second_amount - budget) else second
            else:
                preferred = first
            preferred_label = str(preferred.get("label") or preferred.get("product_name") or "the first option")
            first_angle = "looks like the stronger pick if you want the more polished option"
            second_angle = "is the easier pick if keeping the spend tighter matters more"
            if archetype == "premium_buyer":
                first_angle = "looks like the stronger overall pick if quality and finish matter most"
                second_angle = "still works if you want to spend less, but it’s the more practical choice"
            elif archetype in {"budget_buyer", "campaign_buyer"}:
                first_angle = "feels like the more polished option"
                second_angle = "is the easier value move if keeping the spend tighter matters more"
            elif archetype == "convenience_buyer":
                first_angle = "is the cleaner pick if you want the safer decision quickly"
                second_angle = "is the simpler value option if price matters more than finish"
            return (
                f"{prefix}Between {first_label}"
                + (f" at {first_price}" if first_price else "")
                + f" and {second_label}"
                + (f" at {second_price}" if second_price else "")
                + f", {first_angle}, while {second_label} {second_angle}. "
                + (f"Based on what you told me about {self._preference_summary(preferences)}, I’d lean to {preferred_label}. " if preferences else f"I’d lean to {preferred_label}. ")
                + f"{persuasion.get('comparison_tail', '')} If you want, I can move that one forward or help you decide in one more quick message."
            )

        if re.search(r"\b(later|think about it|let me think|maybe later|not sure|i'll come back)\b", lower):
            self._update_negotiation_memory(conversation, hesitation=True, last_move="hesitation_soft_hold")
            source_line = ""
            if lead_context.get("source") and lead_context.get("source_type") in {"campaign", "content"}:
                source_line = f" Since you came in from our {lead_context.get('source')} {lead_context.get('source_type')}, I can keep this simple."
            if focus_label:
                next_step = "If you want, I can either compare it quickly with the closest alternative or get a draft order ready so you don’t have to repeat everything later."
                if archetype == "premium_buyer":
                    next_step = "If you want, I can quickly tell you why it’s the stronger pick versus the nearest alternative, or I can get a draft order ready so you don’t have to restart later."
                elif archetype in {"budget_buyer", "campaign_buyer"}:
                    next_step = "If you want, I can quickly compare it with the best lower-price alternative, or get a draft order ready so you don’t have to repeat everything later."
                elif archetype == "repeat_buyer":
                    next_step = "If you want, I can keep this easy and either line up the draft order now or compare it with the closest alternative in one quick message."
                return (
                    f"No problem — take your time.{source_line} Based on what you shared, {focus_label} still looks like the strongest fit so far. "
                    + next_step
                )
            if recent_choices:
                return (
                    f"No problem — take your time.{source_line} Your shortlist is still here. "
                    "If you want, I can tell you which of the top options is the better pick for your budget and use case, so deciding later is easier."
                )

        return ""

    def _policy_text_for_message(self, playbook: AssistantPlaybookModel, inbound_text: str) -> str:
        lower = inbound_text.lower()
        policies = {**DEFAULT_POLICIES, **(playbook.policy_json or {})}
        policy_keys: list[str] = []
        if re.search(r"\b(return|returns|exchange|fit|refund)\b", lower):
            policy_keys.append("returns")
        if re.search(r"\b(delivery|deliver|shipping|ship|courier)\b", lower):
            policy_keys.append("delivery")
        if re.search(r"\b(payment|pay|card|cash|cod)\b", lower):
            policy_keys.append("payment")
        if re.search(r"\b(warranty|guarantee)\b", lower):
            policy_keys.append("warranty")
        if re.search(r"\b(discount|discounts|offer|offers|promo|coupon)\b", lower):
            policy_keys.append("discounts")
        if not policy_keys:
            return ""
        labels = {
            "returns": "Return policy",
            "delivery": "Delivery policy",
            "payment": "Payment policy",
            "warranty": "Warranty policy",
            "discounts": "Discount policy",
        }
        replies = []
        for policy_key in policy_keys:
            policy = str(policies.get(policy_key) or "").strip()
            if policy:
                replies.append(f"{labels[policy_key]}: {policy}")
        if replies:
            return " ".join(replies)
        return "I do not want to guess the store policy here; I can ask a team member to confirm it for you."

    def _remembered_variant_for_message(
        self,
        conversation: CustomerConversationModel,
        inbound_text: str,
    ) -> dict[str, Any] | None:
        memory = self._memory(conversation)
        recent_choices = memory.get("recent_choices")
        if isinstance(recent_choices, list):
            lower = inbound_text.lower()
            ordinal_index: int | None = None
            if re.search(r"\b(first|1st|option 1|number 1)\b", lower):
                ordinal_index = 0
            elif re.search(r"\b(second|2nd|option 2|number 2)\b", lower):
                ordinal_index = 1
            elif re.search(r"\b(third|3rd|option 3|number 3)\b", lower):
                ordinal_index = 2
            if ordinal_index is not None and ordinal_index < len(recent_choices) and isinstance(recent_choices[ordinal_index], dict):
                return dict(recent_choices[ordinal_index])

        variant = memory.get("last_variant")
        if not isinstance(variant, dict) or not variant.get("variant_id"):
            return None
        lower = inbound_text.lower()
        if re.search(
            r"\b(it|that|this|same one|same item|that one|take it|book it|reserve it|price again|what was the price)\b",
            lower,
        ):
            return dict(variant)
        if self._catalog_intent_flags(inbound_text)[2] and re.search(
            r"\b(draft order|prepare(?: a)?(?: draft)? order|make(?: the| an| a)? order|place(?: the| an| a)? order)\b",
            lower,
        ):
            return dict(variant)
        if self._catalog_intent_flags(inbound_text)[2] and not self._catalog_search_queries(inbound_text):
            return dict(variant)
        return None

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
        return any(self._catalog_intent_flags(text)) or bool(CATALOG_LOOKUP_RE.search(text.lower()) and self._catalog_search_queries(text))

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

        price_intent, stock_intent, order_intent = self._catalog_intent_flags(inbound_text)
        lookup_intent = bool(CATALOG_LOOKUP_RE.search(inbound_text.lower()))
        tool_names: list[str] = []
        remembered_variant = self._remembered_variant_for_message(conversation, inbound_text)
        if remembered_variant is not None:
            variant_id = str(remembered_variant.get("variant_id") or "").strip()
            search_result = {
                "ok": True,
                "location_id": remembered_variant.get("location_id") or "",
                "items": [remembered_variant],
            }
            availability_result = None
            price_result = None
            if variant_id and (stock_intent or order_intent or lookup_intent):
                availability_result = self._execute_and_record_tool(
                    session,
                    tool_name="get_variant_availability",
                    arguments={"variant_id": variant_id, "location_id": remembered_variant.get("location_id") or ""},
                    channel=channel,
                    conversation=conversation,
                    run=run,
                )
                tool_names.append("get_variant_availability")
            if variant_id and (price_intent or order_intent):
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
                query=str(remembered_variant.get("sku") or remembered_variant.get("label") or "previous item"),
                tool_names=tuple(tool_names),
                search_result=search_result,
                availability_result=availability_result,
                price_result=price_result,
            )

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
        availability_result = None
        price_result = None
        if len(items) == 1:
            variant_id = str(items[0].get("variant_id") or "").strip()
            if variant_id and (stock_intent or order_intent or lookup_intent):
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
        conversation: CustomerConversationModel,
        inbound_text: str,
        grounding: CatalogGrounding,
    ) -> str:
        price_intent, stock_intent, order_intent = self._catalog_intent_flags(inbound_text)
        lookup_intent = bool(CATALOG_LOOKUP_RE.search(inbound_text.lower()))
        if not (price_intent or stock_intent or order_intent or lookup_intent):
            return ""

        items = list(grounding.search_result.get("items") or [])
        policy_text = self._policy_text_for_message(playbook, inbound_text)
        policy_suffix = f" {policy_text}" if policy_text else ""
        health_prefix = ""
        if playbook.business_type == "pet_food" and self._has_risk_terms(inbound_text.lower()):
            health_prefix = "Because you mentioned a health concern, please check with a veterinarian before changing food. "

        if not items:
            query = grounding.query or "that item"
            return (
                f"{health_prefix}I checked the catalog for {query}, but I don’t see a confident active match yet. "
                f"Send the product name, size, color, flavor, device model, or SKU and I’ll tighten it up for you.{policy_suffix}"
            )


        if len(items) > 1:
            choices = [
                self._catalog_choice_summary(item, client)
                for item in items[:3]
            ]
            prefix = self._continuity_prefix(conversation, warm=True)
            return (
                f"{health_prefix}{prefix}I found a few close matches:\n"
                + self._numbered_options(choices)
                + f"\nTell me the option number, or the size / color / SKU you want and I’ll keep it moving.{policy_suffix}"
            )

        variant = (grounding.availability_result or {}).get("variant") or items[0]
        price_variant = (grounding.price_result or {}).get("variant") or variant
        label = str(variant.get("label") or variant.get("product_name") or "that item")
        sku = str(variant.get("sku") or "").strip()
        sku_text = f" (SKU {sku})" if sku else ""

        available = as_decimal(variant.get("available_to_sell") or ZERO)
        qty_text = self._format_quantity(available)
        price_text = ""
        unit_price = price_variant.get("unit_price")
        if unit_price is not None:
            price_text = self._format_money(unit_price, client)

        if available <= ZERO:
            prefix = self._continuity_prefix(conversation)
            return (
                f"{health_prefix}{prefix}{label}{sku_text} is out of stock right now. "
                f"If you want, I can suggest the closest available alternative for you.{policy_suffix}"
            )

        if price_intent and (stock_intent or lookup_intent or order_intent) and price_text:
            prefix = self._continuity_prefix(conversation)
            return (
                f"{health_prefix}{prefix}Yes — {label}{sku_text} is available, and I can see {qty_text} ready to sell. "
                f"The current price is {price_text}. "
                f"If you want, I can prepare a draft order or show the closest cheaper alternative.{policy_suffix}"
            )
        strategy = self._conversation_strategy_snapshot(conversation, inbound_text)
        archetype = str(strategy.get("buyer_archetype") or self._buyer_archetype(conversation, inbound_text))
        if stock_intent or order_intent or lookup_intent:
            prefix = self._continuity_prefix(conversation)
            if strategy.get("next_best_action") == "prepare_or_advance_order":
                next_step = "If you want, I can prepare the draft order now for staff review."
            elif strategy.get("next_best_action") == "answer_facts_then_soft_close":
                next_step = "If you want, I can prepare a draft order or show the closest cheaper alternative so you can decide quickly."
            else:
                next_step = "If you want, I can also check the price or prepare a draft order."
            if archetype == "premium_buyer":
                next_step = "If you want, I can prepare the draft order or compare it with the nearest alternative so you can choose the stronger option confidently."
            elif archetype in {"budget_buyer", "campaign_buyer"} and strategy.get("next_best_action") != "prepare_or_advance_order":
                next_step = "If you want, I can prepare a draft order or show the closest cheaper alternative so the decision stays easy."
            elif archetype == "repeat_buyer":
                next_step = "If you want, I can move straight to the draft order so you don’t have to repeat the details."
            return f"{health_prefix}{prefix}Yes — {label}{sku_text} is available, and I can see {qty_text} ready to sell. {next_step}{policy_suffix}"
        if price_intent:
            prefix = self._continuity_prefix(conversation)
            if price_text:
                if strategy.get("next_best_action") == "handle_price_objection_and_soft_close":
                    return f"{health_prefix}{prefix}{label}{sku_text} is currently {price_text}. If price is the main thing, I can also show the closest cheaper alternative or get the draft order moving for you.{policy_suffix}"
                if archetype == "premium_buyer":
                    return f"{health_prefix}{prefix}{label}{sku_text} is currently {price_text}. If you want, I can also compare it with the nearest alternative so you can see whether it’s the stronger overall pick.{policy_suffix}"
                if archetype in {"budget_buyer", "campaign_buyer"}:
                    return f"{health_prefix}{prefix}{label}{sku_text} is currently {price_text}. If you want, I can also show the closest lower-price alternative or help you move this one forward.{policy_suffix}"
                return f"{health_prefix}{prefix}{label}{sku_text} is currently {price_text}. If you want, I can also check stock or help you compare it with the closest alternative.{policy_suffix}"
            return f"{health_prefix}{prefix}I found {label}{sku_text}, but I do not see a saved selling price for it yet. I can ask staff to confirm it for you.{policy_suffix}"

        prefix = self._continuity_prefix(conversation)
        return f"{health_prefix}{prefix}I found {label}{sku_text}. If you want, I can check stock, price, or prepare the next step for you.{policy_suffix}"

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
                "Personality: natural, warm, observant, concise, helpful, and commercially sensible without sounding scripted.",
                f"Brand personality: {playbook.brand_personality}. Channel: {channel.provider}.",
                "Conversation flow: understand intent, continue naturally from prior context, use remembered buyer signals, buyer archetype, lead source, language, and message modality when helpful, ask one useful clarifying question only when needed, call tools for facts, answer clearly, then offer one smart next step.",
                "Sound like a top store salesperson who remembers the shopper, understands buying intent, adapts style to the buyer, and reduces friction without sounding pushy or scripted.",
                "Customers may write in messy, random, mixed, or multi-turn ways. Follow meaning, not a rigid flowchart.",
                "When the customer's language is clear, answer in that language. If they switch language, adapt.",
                "If they refer to an image or screenshot and no vision tool is available, do not pretend you saw it. Ask for the exact detail you should focus on.",
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
            memory_json={"thread_graph": {}, "customer_journey": {}, "sales_state": {}},
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
