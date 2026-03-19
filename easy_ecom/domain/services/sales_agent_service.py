from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.rbac import default_page_names_for_roles
from easy_ecom.core.security import hash_token, new_token
from easy_ecom.core.slugs import slugify_identifier
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import (
    AiReviewDraftModel,
    AuditLogModel,
    ChannelConversationModel,
    ChannelIntegrationModel,
    ChannelJobModel,
    ChannelMessageModel,
    ChannelMessageProductMentionModel,
    ClientModel,
    ClientSettingsModel,
    CustomerModel,
    LocationModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnModel,
    TenantAgentProfileModel,
    UserModel,
    UserRoleModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.commerce_service import (
    CommerceBaseService,
    MONEY_QUANTUM,
    SalesService,
    ZERO,
    as_decimal,
    as_optional_decimal,
    build_variant_label,
    derive_discount_percent,
    normalize_email,
    normalize_phone,
)


REPLY_REVIEW_REASONS = {
    "discount_request",
    "complaint",
    "return_request",
    "payment_issue",
    "missing_price",
    "low_confidence",
}
BUSINESS_INFO_PHRASES = (
    "shop name",
    "store name",
    "business name",
    "company name",
    "what is your shop name",
    "what's your shop name",
    "what is your store name",
    "what's your store name",
    "who are you",
)
ALLOWED_BEHAVIOR_TAGS = {
    "price_sensitive",
    "discount_seeking",
    "comparison_shopper",
    "upsell_receptive",
    "urgent_buyer",
}
PURCHASE_KEYWORDS = ("buy", "order", "take", "need", "want", "book", "reserve")
PRICE_KEYWORDS = ("price", "cost", "how much", "rate")
AVAILABILITY_KEYWORDS = ("available", "availability", "in stock", "have")
REVIEW_KEYWORDS = {
    "complaint": ("complaint", "bad", "angry", "issue", "problem"),
    "return_request": ("return", "refund", "exchange"),
    "payment_issue": ("payment", "paid", "transfer", "receipt"),
    "discount_request": ("discount", "less", "best price", "offer", "cheap", "deal"),
}
GREETING_KEYWORDS = ("hello", "hi", "hey", "good morning", "good afternoon", "good evening", "salam")
MATCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "anything",
    "are",
    "at",
    "available",
    "availability",
    "be",
    "best",
    "cost",
    "do",
    "does",
    "for",
    "good",
    "have",
    "hello",
    "hey",
    "hi",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "morning",
    "much",
    "my",
    "need",
    "name",
    "of",
    "on",
    "or",
    "please",
    "price",
    "products",
    "salam",
    "show",
    "stock",
    "store",
    "tell",
    "there",
    "the",
    "to",
    "today",
    "want",
    "what",
    "which",
    "with",
    "you",
    "your",
    "shop",
    "asking",
    "else",
    "exact",
    "nothing",
}
SIZE_MATCH_TOKENS = {"xs", "s", "m", "l", "xl", "xxl", "xxxl"}
COLOR_TOKENS = (
    "black",
    "white",
    "blue",
    "red",
    "green",
    "yellow",
    "pink",
    "brown",
    "beige",
    "grey",
    "gray",
    "navy",
)
PERCENT_QUANTUM = Decimal("0.01")
FACTS_SUMMARY_LIMIT = 600
MAX_RECENT_TURNS = 4
MAX_PRIMARY_MATCHES = 3
MAX_ALTERNATIVE_MATCHES = 2
MAX_UPSELL_MATCHES = 2


@dataclass(frozen=True)
class MatchedVariant:
    variant_id: str
    product_id: str
    product_name: str
    brand: str
    label: str
    sku: str
    available_to_sell: Decimal
    unit_price: Decimal
    min_price: Decimal | None
    match_score: int


@dataclass(frozen=True)
class ConversationTurn:
    speaker: str
    text: str


@dataclass(frozen=True)
class ConversationMemorySnapshot:
    summary: str
    recent_turns: tuple[ConversationTurn, ...]


@dataclass(frozen=True)
class CustomerSnapshot:
    customer_id: str | None
    customer_name: str
    customer_phone: str
    customer_type: str
    behavior_tags: tuple[str, ...]
    lifetime_spend: Decimal
    lifetime_order_count: int
    last_order_at: str | None


@dataclass(frozen=True)
class WarehouseSearchRequest:
    client_id: str
    location_id: str
    message_text: str
    normalized_text: str
    tokens: tuple[str, ...]
    intent: str
    quantity: Decimal


@dataclass(frozen=True)
class OfferBand:
    offer_id: str
    label: str
    unit_price: Decimal
    discount_percent: Decimal
    requires_review: bool


@dataclass(frozen=True)
class OfferPolicy:
    list_price: Decimal | None
    floor_price: Decimal | None
    preferred_close_price: Decimal | None
    selected_offer_id: str | None
    selected_unit_price: Decimal | None
    requires_discount_approval: bool
    discount_requested: bool
    auto_discount_steps: tuple[OfferBand, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class WarehouseFactsPack:
    intent: str
    business_name: str
    search_request: WarehouseSearchRequest
    customer_snapshot: CustomerSnapshot
    conversation_memory: ConversationMemorySnapshot
    primary_matches: tuple[MatchedVariant, ...]
    alternatives: tuple[MatchedVariant, ...]
    upsell_candidates: tuple[MatchedVariant, ...]
    offer_policy: OfferPolicy
    stock_scope: str
    next_required_action: str
    helper_used: bool
    helper_summary: str
    clarifier_options: tuple[str, ...]
    behavior_tags: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class SalesReplyDecision:
    intent: str
    reply_text: str
    reply_mode: str
    confidence: Decimal
    selected_variant_id: str | None
    selected_offer_id: str | None
    recommended_variant_ids: tuple[str, ...]
    needs_review: bool
    reason_codes: tuple[str, ...]
    behavior_tags: tuple[str, ...]
    draft_order_request: dict[str, Any] | None
    helper_used: bool
    sales_model_used: bool


class NegotiationPolicyService:
    def build_policy(
        self,
        *,
        lead_match: MatchedVariant | None,
        client_settings: ClientSettingsModel | None,
        base_reason_codes: tuple[str, ...],
    ) -> OfferPolicy:
        requires_discount_approval = bool(client_settings.require_discount_approval) if client_settings else False
        discount_requested = "discount_request" in base_reason_codes
        if lead_match is None:
            return OfferPolicy(
                list_price=None,
                floor_price=None,
                preferred_close_price=None,
                selected_offer_id=None,
                selected_unit_price=None,
                requires_discount_approval=requires_discount_approval,
                discount_requested=discount_requested,
                auto_discount_steps=(),
                reason_codes=tuple(sorted(set(base_reason_codes))),
            )

        list_price = lead_match.unit_price.quantize(MONEY_QUANTUM)
        floor_price = (lead_match.min_price or lead_match.unit_price).quantize(MONEY_QUANTUM)
        if floor_price > list_price:
            floor_price = list_price
        max_discount_percent = derive_discount_percent(list_price, floor_price) or ZERO
        steps: list[OfferBand] = [
            OfferBand(
                offer_id="list_price",
                label="List price",
                unit_price=list_price,
                discount_percent=ZERO,
                requires_review=False,
            )
        ]

        preferred_close_price = list_price
        if floor_price < list_price:
            allowed_span = (list_price - floor_price).quantize(MONEY_QUANTUM)
            preferred_reduction = min(
                allowed_span / Decimal("2"),
                (list_price * Decimal("0.03")).quantize(MONEY_QUANTUM),
            )
            preferred_close_price = (list_price - preferred_reduction).quantize(MONEY_QUANTUM)
            if preferred_close_price < floor_price:
                preferred_close_price = floor_price
            if preferred_close_price < list_price:
                steps.append(
                    OfferBand(
                        offer_id="preferred_close",
                        label="Preferred close",
                        unit_price=preferred_close_price,
                        discount_percent=derive_discount_percent(list_price, preferred_close_price) or ZERO,
                        requires_review=False,
                    )
                )
            if floor_price not in {band.unit_price for band in steps}:
                steps.append(
                    OfferBand(
                        offer_id="floor_price",
                        label="Floor price",
                        unit_price=floor_price,
                        discount_percent=max_discount_percent,
                        requires_review=requires_discount_approval,
                    )
                )

        selected_offer_id = "list_price"
        selected_unit_price = list_price
        reason_codes = set(base_reason_codes)
        if discount_requested:
            if requires_discount_approval:
                reason_codes.add("discount_request")
            elif any(band.offer_id == "preferred_close" for band in steps):
                selected_offer_id = "preferred_close"
                selected_unit_price = next(band.unit_price for band in steps if band.offer_id == selected_offer_id)

        return OfferPolicy(
            list_price=list_price,
            floor_price=floor_price,
            preferred_close_price=preferred_close_price,
            selected_offer_id=selected_offer_id,
            selected_unit_price=selected_unit_price,
            requires_discount_approval=requires_discount_approval,
            discount_requested=discount_requested,
            auto_discount_steps=tuple(steps),
            reason_codes=tuple(sorted(reason_codes)),
        )


class WarehouseHelperService:
    def __init__(self, service: "SalesAgentService") -> None:
        self._service = service

    def resolve(
        self,
        *,
        model_name: str,
        message_text: str,
        memory: ConversationMemorySnapshot,
        candidates: list[MatchedVariant],
    ) -> tuple[list[MatchedVariant], str, tuple[str, ...], bool]:
        ranked = candidates[: MAX_PRIMARY_MATCHES + MAX_ALTERNATIVE_MATCHES]
        if len(ranked) <= 1:
            return ranked, "", (), False

        fallback_clarifiers = tuple(item.label for item in ranked[:2])
        payload = self._service._helper_rank_candidates_with_model(
            model_name=model_name,
            message_text=message_text,
            memory=memory,
            candidates=ranked,
        )
        if payload is None:
            return ranked, "", fallback_clarifiers, False

        allowed = {item.variant_id: item for item in ranked}
        ordered: list[MatchedVariant] = []
        for variant_id in payload.get("ranked_variant_ids", []):
            record = allowed.get(str(variant_id))
            if record is not None and record not in ordered:
                ordered.append(record)
        for item in ranked:
            if item not in ordered:
                ordered.append(item)
        clarifiers = tuple(
            str(option).strip()
            for option in payload.get("clarifier_options", [])
            if str(option).strip()
        )[:2] or fallback_clarifiers
        return ordered, str(payload.get("summary", "")).strip(), clarifiers, True


class WarehouseContextService:
    def __init__(self, service: "SalesAgentService", session: Session) -> None:
        self._service = service
        self._session = session
        self._policy = NegotiationPolicyService()
        self._helper = WarehouseHelperService(service)

    def build_facts_pack(
        self,
        *,
        integration: ChannelIntegrationModel,
        conversation: ChannelConversationModel,
        inbound_message: ChannelMessageModel,
        customer: CustomerModel | None,
    ) -> WarehouseFactsPack:
        text = inbound_message.message_text or ""
        intent, behavior_tags, base_reason_codes = self._service._message_signals(text)
        business_name = self._service._client_business_name(self._session, integration.client_id) or integration.display_name or "our store"
        location_id = str(integration.default_location_id or self._service._default_location_id(self._session, integration.client_id))
        search_request = WarehouseSearchRequest(
            client_id=integration.client_id,
            location_id=location_id,
            message_text=text,
            normalized_text=" ".join(text.strip().lower().split()),
            tokens=self._service._search_tokens(text),
            intent=intent,
            quantity=self._service._extract_quantity(text.lower()),
        )
        customer_snapshot = self._service._customer_snapshot(conversation, customer)
        memory = self._service._conversation_memory_snapshot(self._session, conversation.conversation_id)
        matches = (
            self._service._match_variants(self._session, integration.client_id, location_id, text)
            if intent not in {"business_info", "greeting"}
            else []
        )

        helper_summary = ""
        clarifier_options: tuple[str, ...] = ()
        helper_used = False
        if self._service._should_use_helper(search_request, matches):
            matches, helper_summary, clarifier_options, helper_used = self._helper.resolve(
                model_name=settings.openai_helper_model,
                message_text=text,
                memory=memory,
                candidates=matches,
            )

        primary_matches, alternatives = self._service._split_match_candidates(search_request, matches, helper_used)
        upsell_candidates: tuple[MatchedVariant, ...] = ()
        if primary_matches and intent != "greeting":
            upsell_candidates = tuple(
                self._service._upsell_candidates(
                    self._session,
                    integration.client_id,
                    location_id,
                    {item.variant_id for item in (*primary_matches, *alternatives)},
                )[:MAX_UPSELL_MATCHES]
            )

        client_settings = self._service._client_settings(self._session, integration.client_id)
        offer_policy = self._policy.build_policy(
            lead_match=primary_matches[0] if primary_matches else None,
            client_settings=client_settings,
            base_reason_codes=base_reason_codes,
        )
        reason_codes = self._service._facts_reason_codes(
            search_request=search_request,
            primary_matches=primary_matches,
            alternatives=alternatives,
            offer_policy=offer_policy,
        )
        next_required_action = self._service._next_required_action(
            search_request=search_request,
            primary_matches=primary_matches,
            reason_codes=reason_codes,
            offer_policy=offer_policy,
        )
        return WarehouseFactsPack(
            intent=intent,
            business_name=business_name,
            search_request=search_request,
            customer_snapshot=customer_snapshot,
            conversation_memory=memory,
            primary_matches=primary_matches,
            alternatives=alternatives,
            upsell_candidates=upsell_candidates,
            offer_policy=offer_policy,
            stock_scope="default_location_only",
            next_required_action=next_required_action,
            helper_used=helper_used,
            helper_summary=helper_summary,
            clarifier_options=clarifier_options,
            behavior_tags=behavior_tags,
            reason_codes=reason_codes,
        )


class SalesConversationService:
    def __init__(self, service: "SalesAgentService") -> None:
        self._service = service

    def build_reply(self, *, facts_pack: WarehouseFactsPack, model_name: str) -> SalesReplyDecision:
        fallback = self._service._deterministic_reply_from_facts(facts_pack)
        if not self._service._should_use_sales_model(facts_pack, fallback):
            return fallback
        return self._service._sales_reply_with_model(
            model_name=model_name,
            facts_pack=facts_pack,
            fallback=fallback,
        )


class SalesAgentService(CommerceBaseService):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__(session_factory)
        self._sales_service = SalesService(session_factory)

    def list_integrations(self, user: AuthenticatedUser, *, target_client_id: str | None = None) -> list[dict[str, Any]]:
        self._require_sales_agent_access(user)
        client_id = self._target_client_id(user, target_client_id)
        with self._session_factory() as session:
            self._ensure_client_exists(session, client_id)
            profile = self._profile_for_client(session, client_id)
            rows = session.execute(
                select(ChannelIntegrationModel)
                .where(ChannelIntegrationModel.client_id == client_id)
                .order_by(ChannelIntegrationModel.created_at.desc())
            ).scalars()
            return [self._integration_payload(item, profile) for item in rows]

    def list_available_locations(
        self,
        user: AuthenticatedUser,
        *,
        target_client_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self._require_owner_or_admin(user)
        client_id = self._target_client_id(user, target_client_id)
        with self._session_factory() as session:
            self._ensure_client_exists(session, client_id)
            rows = session.execute(
                select(LocationModel)
                .where(LocationModel.client_id == client_id, LocationModel.status == "active")
                .order_by(LocationModel.is_default.desc(), LocationModel.name.asc())
            ).scalars()
            return [
                {
                    "location_id": str(item.location_id),
                    "name": item.name,
                    "is_default": item.is_default,
                }
                for item in rows
            ]

    def validate_whatsapp_integration(
        self,
        user: AuthenticatedUser,
        payload: dict[str, Any],
        *,
        target_client_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_owner_or_admin(user)
        client_id = self._target_client_id(user, target_client_id)
        with self._session_factory() as session:
            self._ensure_client_exists(session, client_id)
            existing = session.execute(
                select(ChannelIntegrationModel).where(
                    ChannelIntegrationModel.client_id == client_id,
                    ChannelIntegrationModel.provider == "whatsapp",
                )
            ).scalar_one_or_none()
            access_token_input = str(payload.get("access_token", "")).strip()
            app_secret_input = str(payload.get("app_secret", "")).strip()
            verify_token_input = str(payload.get("verify_token", "")).strip()
            verify_token_set = bool(verify_token_input) or bool(existing.verify_token_hash) if existing is not None else bool(verify_token_input)
            default_location_id = self._clean_uuid(payload.get("default_location_id")) or (
                str(existing.default_location_id) if existing is not None and existing.default_location_id else None
            )
            result = self._run_whatsapp_diagnostics(
                session,
                integration=None,
                client_id=client_id,
                external_account_id=str(payload.get("external_account_id", "")).strip(),
                phone_number_id=str(payload.get("phone_number_id", "")).strip(),
                verify_token_set=verify_token_set,
                access_token=access_token_input or (existing.access_token if existing else ""),
                app_secret=app_secret_input or (existing.app_secret if existing else ""),
                model_name=str(payload.get("model_name", "")).strip() or settings.openai_model,
                default_location_id=default_location_id,
                auto_send_enabled=bool(payload.get("auto_send_enabled")),
                persist=False,
            )
            return {
                "diagnostics": result["diagnostics"],
                "provider_details": result["provider_details"],
            }

    def upsert_whatsapp_integration(
        self,
        user: AuthenticatedUser,
        payload: dict[str, Any],
        *,
        target_client_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_owner_or_admin(user)
        client_id = self._target_client_id(user, target_client_id)
        with self._session_factory() as session:
            self._ensure_client_exists(session, client_id)
            actor_user_id = self._canonical_actor_user_id(session, user, client_id)
            integration = session.execute(
                select(ChannelIntegrationModel).where(
                    ChannelIntegrationModel.client_id == client_id,
                    ChannelIntegrationModel.provider == "whatsapp",
                )
            ).scalar_one_or_none()
            is_new = integration is None
            if integration is None:
                integration = ChannelIntegrationModel(
                    channel_id=new_uuid(),
                    client_id=client_id,
                    provider="whatsapp",
                    webhook_key=new_token(24),
                    created_by_user_id=actor_user_id,
                )
                session.add(integration)

            previous_phone_number_id = integration.phone_number_id
            previous_external_account_id = integration.external_account_id
            previous_access_token = integration.access_token
            previous_app_secret = integration.app_secret
            previous_verify_token_hash = integration.verify_token_hash
            previous_model_name = str(self._integration_base_config(integration).get("model_name", settings.openai_model))

            integration.display_name = str(payload.get("display_name", "")).strip() or "WhatsApp Sales Agent"
            integration.external_account_id = str(payload.get("external_account_id", "")).strip() or str(
                payload.get("phone_number_id", "")
            ).strip()
            integration.phone_number_id = str(payload.get("phone_number_id", "")).strip()
            integration.phone_number = str(payload.get("phone_number", "")).strip()
            verify_token_input = str(payload.get("verify_token") or "").strip()
            setup_verify_token: str | None = None
            if verify_token_input:
                integration.verify_token_hash = hash_token(verify_token_input)
                setup_verify_token = verify_token_input
            elif is_new or not integration.verify_token_hash:
                setup_verify_token = new_token(18)
                integration.verify_token_hash = hash_token(setup_verify_token)

            access_token_input = str(payload.get("access_token") or "").strip()
            if access_token_input:
                integration.access_token = access_token_input
            elif is_new:
                integration.access_token = ""

            app_secret_input = str(payload.get("app_secret") or "").strip()
            if app_secret_input:
                integration.app_secret = app_secret_input
            elif is_new:
                integration.app_secret = ""

            default_location_id = self._clean_uuid(payload.get("default_location_id"))
            integration.default_location_id = default_location_id or None
            integration.auto_send_enabled = bool(payload.get("auto_send_enabled"))
            model_name = str(payload.get("model_name", "")).strip() or settings.openai_model
            persona_prompt = str(payload.get("persona_prompt", "")).strip()
            self._set_integration_config(
                integration,
                model_name=model_name,
                persona_prompt=persona_prompt,
            )
            credentials_changed = any(
                (
                    previous_phone_number_id != integration.phone_number_id,
                    previous_external_account_id != integration.external_account_id,
                    previous_access_token != integration.access_token,
                    previous_app_secret != integration.app_secret,
                    previous_verify_token_hash != integration.verify_token_hash,
                )
            )
            openai_changed = previous_model_name != model_name
            if is_new or credentials_changed or openai_changed:
                self._reset_integration_diagnostics(
                    integration,
                    reset_webhook=is_new or credentials_changed,
                    reset_provider=is_new or credentials_changed,
                    reset_openai=is_new or credentials_changed or openai_changed,
                )
            integration.status = (
                "active"
                if integration.phone_number_id and integration.access_token and integration.verify_token_hash and integration.app_secret
                else "inactive"
            )

            profile = self._profile_for_client(session, client_id)
            if profile is None:
                profile = TenantAgentProfileModel(
                    agent_profile_id=new_uuid(),
                    client_id=client_id,
                )
                session.add(profile)
            profile.channel_id = integration.channel_id
            profile.default_location_id = integration.default_location_id
            profile.is_enabled = bool(payload.get("agent_enabled", True))
            profile.auto_send_enabled = bool(payload.get("auto_send_enabled"))
            profile.model_name = str(payload.get("model_name", "")).strip() or settings.openai_model
            profile.persona_prompt = str(payload.get("persona_prompt", "")).strip()
            profile.behavior_policy_json = {
                "allowed_behavior_tags": sorted(ALLOWED_BEHAVIOR_TAGS),
                "sales_mode": "aggressive_but_honest",
            }

            self._log_audit(
                session,
                client_id=client_id,
                actor_user_id=actor_user_id,
                entity_type="channel_integration",
                entity_id=integration.channel_id,
                action="channel_integration_saved",
                metadata_json={
                    "provider": integration.provider,
                    "phone_number_id": integration.phone_number_id,
                    "auto_send_enabled": integration.auto_send_enabled,
                },
            )
            session.commit()
            return {
                "channel": self._integration_payload(integration, profile),
                "setup_verify_token": setup_verify_token,
            }

    def run_channel_diagnostics(self, user: AuthenticatedUser, channel_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            integration, profile = self._channel_for_owner_or_admin(session, user, channel_id)
            result = self._run_whatsapp_diagnostics(
                session,
                integration=integration,
                client_id=integration.client_id,
                external_account_id=integration.external_account_id,
                phone_number_id=integration.phone_number_id,
                verify_token_set=bool(integration.verify_token_hash),
                access_token=integration.access_token,
                app_secret=integration.app_secret,
                model_name=str(self._integration_base_config(integration).get("model_name", profile.model_name if profile else settings.openai_model)),
                default_location_id=str(integration.default_location_id) if integration.default_location_id else None,
                auto_send_enabled=integration.auto_send_enabled,
                persist=True,
            )
            session.commit()
            return {
                "channel": self._integration_payload(integration, profile),
                "diagnostics": result["diagnostics"],
                "provider_details": result["provider_details"],
            }

    def send_channel_smoke(self, user: AuthenticatedUser, channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._session_factory() as session:
            integration, _profile = self._channel_for_owner_or_admin(session, user, channel_id)
            recipient = normalize_phone(str(payload.get("recipient", "")).strip()) or str(payload.get("recipient", "")).strip()
            self._require(bool(recipient), message="Recipient phone is required", code="RECIPIENT_REQUIRED")
            text = str(payload.get("text", "")).strip() or "EasyEcom smoke test. Reply path is working."
            diagnostics_time = now_utc()
            provider_details: dict[str, Any] = {"recipient": recipient}
            try:
                send_result = self._send_whatsapp_text(integration, recipient, text)
            except Exception as exc:
                provider_status_code = None
                provider_response_excerpt = None
                if isinstance(exc, ApiException):
                    provider_status_code = exc.details.get("provider_status_code") if exc.details else None
                    provider_response_excerpt = exc.details.get("provider_response_excerpt") if exc.details else None
                diagnostics = self._update_integration_diagnostics(
                    integration,
                    outbound_send_ok=False,
                    last_error_code=self._diagnostic_code(exc),
                    last_error_message=str(exc.message if isinstance(exc, ApiException) else exc),
                    last_provider_status_code=provider_status_code,
                    last_provider_response_excerpt=self._bounded_text(provider_response_excerpt),
                    last_diagnostic_at=diagnostics_time.isoformat(),
                )
                self._log_audit(
                    session,
                    client_id=integration.client_id,
                    actor_user_id=self._canonical_actor_user_id(session, user, integration.client_id),
                    entity_type="channel_integration",
                    entity_id=integration.channel_id,
                    action="channel_smoke_send_failed",
                    metadata_json={"recipient": recipient, "error_code": diagnostics.get("last_error_code")},
                )
                session.commit()
                return {
                    "ok": False,
                    "provider_event_id": None,
                    "message": diagnostics.get("last_error_message") or "Smoke send failed",
                    "diagnostics": self._integration_diagnostics_payload(integration),
                    "provider_details": provider_details,
                }

            diagnostics = self._update_integration_diagnostics(
                integration,
                outbound_send_ok=True,
                last_error_code=None,
                last_error_message=None,
                last_provider_status_code=200,
                last_provider_response_excerpt=None,
                last_diagnostic_at=diagnostics_time.isoformat(),
            )
            self._log_audit(
                session,
                client_id=integration.client_id,
                actor_user_id=self._canonical_actor_user_id(session, user, integration.client_id),
                entity_type="channel_integration",
                entity_id=integration.channel_id,
                action="channel_smoke_sent",
                metadata_json={"recipient": recipient, "provider_event_id": str(send_result.get("provider_event_id", ""))},
            )
            session.commit()
            return {
                "ok": True,
                "provider_event_id": str(send_result.get("provider_event_id", "")) or None,
                "message": "Smoke message accepted by WhatsApp.",
                "diagnostics": self._integration_diagnostics_payload(integration),
                "provider_details": provider_details,
            }

    def verify_whatsapp_webhook(self, webhook_key: str, *, mode: str, verify_token: str, challenge: str) -> str:
        with self._session_factory() as session:
            integration = self._integration_by_webhook_key(session, webhook_key)
            if mode != "subscribe" or hash_token(verify_token.strip()) != integration.verify_token_hash:
                raise ApiException(status_code=403, code="WHATSAPP_VERIFY_FAILED", message="Webhook verification failed")
            self._update_integration_diagnostics(
                integration,
                webhook_verified_at=now_utc().isoformat(),
                last_error_code=None,
                last_error_message=None,
                last_diagnostic_at=now_utc().isoformat(),
            )
            session.commit()
            return challenge

    def handle_whatsapp_webhook(
        self,
        webhook_key: str,
        *,
        raw_body: bytes,
        signature: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            integration = self._integration_by_webhook_key(session, webhook_key)
            webhook_seen_at = now_utc().isoformat()
            self._update_integration_diagnostics(
                integration,
                last_webhook_post_at=webhook_seen_at,
                last_diagnostic_at=webhook_seen_at,
            )
            try:
                self._verify_signature(integration, raw_body, signature)
            except ApiException as exc:
                self._update_integration_diagnostics(
                    integration,
                    signature_validation_ok=False,
                    last_error_code=self._diagnostic_code(exc),
                    last_error_message=exc.message,
                    last_provider_status_code=None,
                    last_provider_response_excerpt=None,
                    last_diagnostic_at=now_utc().isoformat(),
                )
                session.commit()
                raise

            self._update_integration_diagnostics(
                integration,
                signature_validation_ok=True,
                last_error_code=None,
                last_error_message=None,
                last_diagnostic_at=now_utc().isoformat(),
            )
            processed_messages = 0
            updated_statuses = 0
            failed_messages = 0

            for change in self._iter_whatsapp_changes(payload):
                value = change.get("value") or {}
                for status_payload in value.get("statuses") or []:
                    updated_statuses += self._apply_status_update(session, integration, status_payload)
                for inbound_payload in value.get("messages") or []:
                    if str(inbound_payload.get("type", "")).strip() != "text":
                        continue
                    provider_event_id = str(inbound_payload.get("id", "")).strip()
                    try:
                        with session.begin_nested():
                            if provider_event_id and session.execute(
                                select(ChannelMessageModel).where(
                                    ChannelMessageModel.client_id == integration.client_id,
                                    ChannelMessageModel.provider_event_id == provider_event_id,
                                )
                            ).scalar_one_or_none():
                                continue
                            self._process_inbound_payload(session, integration, value, inbound_payload)
                    except IntegrityError as exc:
                        if provider_event_id and self._is_duplicate_provider_event_error(exc):
                            continue
                        failed_messages += 1
                        self._update_integration_diagnostics(
                            integration,
                            last_error_code="webhook_persistence_failed",
                            last_error_message=str(exc),
                            last_diagnostic_at=now_utc().isoformat(),
                        )
                    except Exception as exc:
                        failed_messages += 1
                        self._update_integration_diagnostics(
                            integration,
                            last_error_code=self._diagnostic_code(exc),
                            last_error_message=str(exc),
                            last_diagnostic_at=now_utc().isoformat(),
                        )
                    else:
                        processed_messages += 1

            session.commit()
            return {
                "ok": True,
                "processed_messages": processed_messages,
                "updated_statuses": updated_statuses,
                "failed_messages": failed_messages,
            }

    def list_conversations(
        self,
        user: AuthenticatedUser,
        *,
        query: str = "",
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        self._require_sales_agent_access(user)
        with self._session_factory() as session:
            stmt = select(ChannelConversationModel).where(ChannelConversationModel.client_id == user.client_id)
            if status:
                stmt = stmt.where(ChannelConversationModel.status == status)
            trimmed = query.strip().lower()
            if trimmed:
                pattern = f"%{trimmed}%"
                stmt = stmt.where(
                    or_(
                        func.lower(ChannelConversationModel.customer_name_snapshot).like(pattern),
                        func.lower(ChannelConversationModel.customer_phone_snapshot).like(pattern),
                        func.lower(ChannelConversationModel.customer_email_snapshot).like(pattern),
                        func.lower(ChannelConversationModel.external_sender_phone).like(pattern),
                        func.lower(ChannelConversationModel.last_message_preview).like(pattern),
                    )
                )
            rows = session.execute(
                stmt.order_by(ChannelConversationModel.last_message_at.desc(), ChannelConversationModel.updated_at.desc())
            ).scalars()
            items = []
            for record in rows:
                latest_draft = self._latest_draft(session, record.conversation_id)
                linked_order = self._linked_order_payload(session, record.linked_draft_order_id)
                items.append(self._conversation_summary_payload(record, latest_draft, linked_order))
            return items

    def get_conversation_detail(self, user: AuthenticatedUser, conversation_id: str) -> dict[str, Any]:
        self._require_sales_agent_access(user)
        with self._session_factory() as session:
            record = session.execute(
                select(ChannelConversationModel).where(
                    ChannelConversationModel.client_id == user.client_id,
                    ChannelConversationModel.conversation_id == conversation_id,
                )
            ).scalar_one_or_none()
            self._require(record is not None, message="Conversation not found", code="CONVERSATION_NOT_FOUND", status_code=404)
            latest_draft = self._latest_draft(session, record.conversation_id)
            linked_order = self._linked_order_payload(session, record.linked_draft_order_id)
            messages = []
            for message in session.execute(
                select(ChannelMessageModel)
                .where(
                    ChannelMessageModel.client_id == user.client_id,
                    ChannelMessageModel.conversation_id == conversation_id,
                )
                .order_by(ChannelMessageModel.occurred_at.asc(), ChannelMessageModel.created_at.asc())
            ).scalars():
                mentions = self._message_mentions_payload(session, message.message_id)
                messages.append(
                    {
                        "message_id": str(message.message_id),
                        "direction": message.direction,
                        "message_text": message.message_text,
                        "content_summary": message.content_summary,
                        "occurred_at": message.occurred_at.isoformat(),
                        "outbound_status": message.outbound_status,
                        "provider_status": message.provider_status,
                        "mentions": mentions,
                    }
                )
            return {
                **self._conversation_summary_payload(record, latest_draft, linked_order),
                "messages": messages,
                "latest_draft": self._draft_payload(latest_draft) if latest_draft else None,
                "linked_order": linked_order,
            }

    def handoff_conversation(self, user: AuthenticatedUser, conversation_id: str, *, notes: str = "") -> dict[str, Any]:
        self._require_sales_agent_access(user)
        with self._session_factory() as session:
            record = self._conversation_for_update(session, user.client_id, conversation_id)
            record.status = "handoff"
            record.handoff_requested_at = now_utc()
            metadata = dict(record.metadata_json or {})
            if notes.strip():
                metadata["handoff_notes"] = notes.strip()
            record.metadata_json = metadata
            self._log_audit(
                session,
                client_id=user.client_id,
                actor_user_id=user.user_id,
                entity_type="channel_conversation",
                entity_id=record.conversation_id,
                action="sales_agent_handoff",
                metadata_json={"notes": notes.strip()},
            )
            session.commit()
            latest_draft = self._latest_draft(session, record.conversation_id)
            linked_order = self._linked_order_payload(session, record.linked_draft_order_id)
            return self._conversation_summary_payload(record, latest_draft, linked_order)

    def approve_and_send_draft(self, user: AuthenticatedUser, draft_id: str, *, edited_text: str = "") -> dict[str, Any]:
        self._require_sales_agent_access(user)
        with self._session_factory() as session:
            draft = session.execute(
                select(AiReviewDraftModel).where(
                    AiReviewDraftModel.client_id == user.client_id,
                    AiReviewDraftModel.draft_id == draft_id,
                )
            ).scalar_one_or_none()
            self._require(draft is not None, message="Draft not found", code="DRAFT_NOT_FOUND", status_code=404)
            conversation = self._conversation_for_update(session, user.client_id, str(draft.conversation_id))
            integration = session.execute(
                select(ChannelIntegrationModel).where(
                    ChannelIntegrationModel.client_id == user.client_id,
                    ChannelIntegrationModel.channel_id == conversation.channel_id,
                )
            ).scalar_one()
            outbound_text = edited_text.strip() or draft.final_text.strip() or draft.ai_draft_text.strip()
            self._require(bool(outbound_text), message="Draft reply text is required")
            send_result = self._send_whatsapp_text(integration, conversation.external_sender_id, outbound_text)
            outbound_message = ChannelMessageModel(
                message_id=new_uuid(),
                client_id=user.client_id,
                conversation_id=conversation.conversation_id,
                channel_id=integration.channel_id,
                direction="outbound",
                external_sender_id=conversation.external_sender_id,
                provider_event_id=str(send_result.get("provider_event_id", "")),
                provider_status="accepted",
                message_text=outbound_text,
                content_summary=self._summarize_text(outbound_text),
                raw_payload_json=send_result,
                occurred_at=now_utc(),
                outbound_status="sent",
            )
            session.add(outbound_message)
            draft.edited_text = edited_text.strip()
            draft.final_text = outbound_text
            draft.status = "sent"
            draft.approved_by_user_id = user.user_id
            draft.sent_by_user_id = user.user_id
            draft.approved_at = now_utc()
            draft.sent_at = draft.approved_at
            draft.send_result_json = send_result
            draft.human_modified = bool(edited_text.strip())
            conversation.status = "open"
            conversation.last_message_at = outbound_message.occurred_at
            conversation.last_message_preview = outbound_message.content_summary
            integration.last_outbound_at = outbound_message.occurred_at
            self._log_audit(
                session,
                client_id=user.client_id,
                actor_user_id=user.user_id,
                entity_type="ai_review_draft",
                entity_id=draft.draft_id,
                action="sales_agent_draft_sent",
                metadata_json={"conversation_id": conversation.conversation_id},
            )
            session.commit()
            return self._draft_payload(draft)

    def reject_draft(self, user: AuthenticatedUser, draft_id: str, *, reason: str = "") -> dict[str, Any]:
        self._require_sales_agent_access(user)
        with self._session_factory() as session:
            draft = session.execute(
                select(AiReviewDraftModel).where(
                    AiReviewDraftModel.client_id == user.client_id,
                    AiReviewDraftModel.draft_id == draft_id,
                )
            ).scalar_one_or_none()
            self._require(draft is not None, message="Draft not found", code="DRAFT_NOT_FOUND", status_code=404)
            draft.status = "rejected"
            draft.failed_reason = reason.strip() or None
            conversation = self._conversation_for_update(session, user.client_id, str(draft.conversation_id))
            conversation.status = "handoff"
            self._log_audit(
                session,
                client_id=user.client_id,
                actor_user_id=user.user_id,
                entity_type="ai_review_draft",
                entity_id=draft.draft_id,
                action="sales_agent_draft_rejected",
                metadata_json={"reason": reason.strip()},
            )
            session.commit()
            return self._draft_payload(draft)

    def list_agent_orders(self, user: AuthenticatedUser, *, status: str | None = None) -> list[dict[str, Any]]:
        self._require_sales_agent_access(user)
        with self._session_factory() as session:
            stmt = select(SalesOrderModel).where(
                SalesOrderModel.client_id == user.client_id,
                SalesOrderModel.source_type == "sales_agent",
            )
            if status:
                stmt = stmt.where(SalesOrderModel.status == status)
            rows = session.execute(stmt.order_by(SalesOrderModel.created_at.desc())).scalars()
            return [self._sales_service._sales_order_payload(session, order) for order in rows]

    def confirm_agent_order(self, user: AuthenticatedUser, sales_order_id: str) -> dict[str, Any]:
        self._require_sales_agent_access(user)
        payload = self._sales_service.confirm_order(user, sales_order_id)
        with self._session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            if order and order.source_conversation_id:
                conversation = session.execute(
                    select(ChannelConversationModel).where(
                        ChannelConversationModel.client_id == user.client_id,
                        ChannelConversationModel.conversation_id == order.source_conversation_id,
                    )
                ).scalar_one_or_none()
                if conversation:
                    conversation.linked_draft_order_status = order.status
            self._log_audit(
                session,
                client_id=user.client_id,
                actor_user_id=user.user_id,
                entity_type="sales_order",
                entity_id=sales_order_id,
                action="sales_agent_order_confirmed",
                metadata_json={"source_type": "sales_agent"},
            )
            session.commit()
        return payload

    def _process_inbound_payload(
        self,
        session: Session,
        integration: ChannelIntegrationModel,
        envelope: dict[str, Any],
        inbound_payload: dict[str, Any],
    ) -> None:
        sender_id = str(inbound_payload.get("from", "")).strip()
        contacts = envelope.get("contacts") or []
        profile_name = ""
        for item in contacts:
            if str(item.get("wa_id", "")).strip() == sender_id:
                profile_name = str((item.get("profile") or {}).get("name", "")).strip()
                break
        customer = self._find_or_create_customer(session, integration.client_id, sender_id, profile_name)
        conversation = self._find_or_create_conversation(session, integration, customer, sender_id)
        occurred_at = now_utc()
        message_text = str(((inbound_payload.get("text") or {}).get("body")) or "").strip()
        inbound_message = ChannelMessageModel(
            message_id=new_uuid(),
            client_id=integration.client_id,
            conversation_id=conversation.conversation_id,
            channel_id=integration.channel_id,
            direction="inbound",
            external_sender_id=sender_id,
            provider_event_id=str(inbound_payload.get("id", "")).strip(),
            provider_status="received",
            message_text=message_text,
            content_summary=self._summarize_text(message_text),
            raw_payload_json=inbound_payload,
            occurred_at=occurred_at,
            outbound_status="received",
        )
        session.add(inbound_message)
        session.flush()
        conversation.last_message_at = occurred_at
        conversation.last_message_preview = inbound_message.content_summary
        conversation.status = "open"
        integration.last_inbound_at = occurred_at
        self._refresh_customer_snapshot(session, conversation)

        job = ChannelJobModel(
            job_id=new_uuid(),
            client_id=integration.client_id,
            channel_id=integration.channel_id,
            conversation_id=conversation.conversation_id,
            message_id=inbound_message.message_id,
            job_type="process_inbound_message",
            status="processing",
            attempts=1,
            scheduled_at=occurred_at,
            started_at=occurred_at,
            payload_json={"provider_event_id": inbound_message.provider_event_id},
        )
        session.add(job)
        try:
            self._handle_inbound_message(session, integration, conversation, inbound_message, customer)
            job.status = "completed"
        except Exception as exc:
            error_code = self._diagnostic_code(exc)
            error_message = exc.message if isinstance(exc, ApiException) else str(exc)
            job.status = "failed"
            job.last_error = f"{error_code}: {error_message}".strip()
            conversation.status = "needs_review"
            conversation.latest_intent = conversation.latest_intent or "manual_review"
            hold_text = "Thanks for your message. A team member will review and reply shortly."
            conversation.latest_summary = self._summarize_text(error_message or hold_text, limit=500)
            if self._latest_draft(session, conversation.conversation_id) is None:
                session.add(
                    AiReviewDraftModel(
                        draft_id=new_uuid(),
                        client_id=integration.client_id,
                        conversation_id=conversation.conversation_id,
                        inbound_message_id=inbound_message.message_id,
                        linked_sales_order_id=None,
                        status="needs_review",
                        ai_draft_text=hold_text,
                        final_text=hold_text,
                        intent="manual_review",
                        confidence=Decimal("0.10"),
                        grounding_json={"reason_codes": [error_code]},
                        reason_codes_json=[error_code],
                        failed_reason=error_message or hold_text,
                    )
                )
            self._update_integration_diagnostics(
                integration,
                last_error_code=error_code,
                last_error_message=error_message or hold_text,
                last_diagnostic_at=now_utc().isoformat(),
            )
        finally:
            job.finished_at = now_utc()

        self._log_audit(
            session,
            client_id=integration.client_id,
            actor_user_id=None,
            entity_type="channel_message",
            entity_id=inbound_message.message_id,
            action="sales_agent_message_received",
            metadata_json={"conversation_id": conversation.conversation_id},
        )

    def _handle_inbound_message(
        self,
        session: Session,
        integration: ChannelIntegrationModel,
        conversation: ChannelConversationModel,
        inbound_message: ChannelMessageModel,
        customer: CustomerModel | None,
    ) -> None:
        model_name = str(self._integration_base_config(integration).get("model_name", settings.openai_model))
        facts_pack = WarehouseContextService(self, session).build_facts_pack(
            integration=integration,
            conversation=conversation,
            inbound_message=inbound_message,
            customer=customer,
        )
        decision = SalesConversationService(self).build_reply(
            facts_pack=facts_pack,
            model_name=model_name,
        )
        decision_trace = self._decision_trace_payload(facts_pack, decision)

        inbound_message.ai_metadata_json = {
            "tier": decision.reply_mode,
            "helper_used": facts_pack.helper_used,
            "sales_model_used": decision.sales_model_used,
            "reason_codes": list(decision.reason_codes),
            "selected_variant_id": decision.selected_variant_id,
            "selected_offer_id": decision.selected_offer_id,
        }
        inbound_message.structured_extraction_json = {
            "intent": facts_pack.intent,
            "tokens": list(facts_pack.search_request.tokens),
            "quantity": str(facts_pack.search_request.quantity),
            "next_required_action": facts_pack.next_required_action,
        }

        metadata = dict(conversation.metadata_json or {})
        metadata["latest_trace"] = decision_trace
        metadata["rolling_summary"] = self._rolling_summary(
            memory=facts_pack.conversation_memory,
            inbound_text=inbound_message.message_text,
            latest_reply=decision.reply_text,
            needs_review=decision.needs_review,
        )
        conversation.metadata_json = metadata
        conversation.latest_intent = decision.intent
        conversation.latest_summary = str(metadata.get("rolling_summary", "")) or self._summarize_text(decision.reply_text, limit=500)
        conversation.last_recommended_products_summary = self._recommended_summary(
            list(facts_pack.primary_matches),
            list(facts_pack.upsell_candidates),
        )
        conversation.behavior_tags_json = list(decision.behavior_tags)
        conversation.behavior_confidence = decision.confidence

        requested_quantity = (
            decision.draft_order_request.get("quantity")
            if decision.draft_order_request and decision.selected_variant_id
            else None
        )
        for row in facts_pack.primary_matches[:MAX_PRIMARY_MATCHES]:
            session.add(
                ChannelMessageProductMentionModel(
                    mention_id=new_uuid(),
                    client_id=integration.client_id,
                    message_id=inbound_message.message_id,
                    conversation_id=conversation.conversation_id,
                    product_id=row.product_id,
                    variant_id=row.variant_id,
                    mention_role="requested",
                    quantity=requested_quantity if decision.selected_variant_id == row.variant_id else None,
                    unit_price_amount=row.unit_price,
                    min_price_amount=row.min_price,
                    available_to_sell_snapshot=row.available_to_sell,
                )
            )

        order = None
        location_id = integration.default_location_id or self._default_location_id(session, integration.client_id)
        if decision.draft_order_request and customer is not None:
            order = self._create_agent_order(
                session,
                integration,
                conversation,
                customer,
                location_id,
                decision.draft_order_request,
            )

        def create_review_draft(*, reason_codes: list[str], failed_reason: str | None = None) -> AiReviewDraftModel:
            draft = AiReviewDraftModel(
                draft_id=new_uuid(),
                client_id=integration.client_id,
                conversation_id=conversation.conversation_id,
                inbound_message_id=inbound_message.message_id,
                linked_sales_order_id=order.sales_order_id if order else None,
                status="needs_review",
                ai_draft_text=decision.reply_text,
                final_text=decision.reply_text,
                intent=decision.intent,
                confidence=decision.confidence,
                grounding_json={
                    "facts_pack": self._facts_pack_payload(facts_pack),
                    "decision": self._decision_payload(decision),
                    "trace": decision_trace,
                    "send_failure": failed_reason or "",
                },
                reason_codes_json=list(reason_codes),
                failed_reason=failed_reason,
            )
            session.add(draft)
            session.flush()
            if order is not None:
                order.source_agent_draft_id = draft.draft_id
            conversation.status = "needs_review"
            return draft

        needs_review = decision.needs_review or not integration.auto_send_enabled
        draft = None
        if needs_review:
            draft = create_review_draft(reason_codes=list(decision.reason_codes))
        else:
            try:
                send_result = self._send_whatsapp_text(integration, conversation.external_sender_id, decision.reply_text)
            except ApiException as exc:
                draft_reason_codes = list(decision.reason_codes)
                if "auto_send_failed" not in draft_reason_codes:
                    draft_reason_codes.append("auto_send_failed")
                draft = create_review_draft(reason_codes=draft_reason_codes, failed_reason=exc.message)
                self._update_integration_diagnostics(
                    integration,
                    outbound_send_ok=False,
                    last_error_code=self._diagnostic_code(exc),
                    last_error_message=exc.message,
                    last_provider_status_code=exc.details.get("provider_status_code") if exc.details else None,
                    last_provider_response_excerpt=exc.details.get("provider_response_excerpt") if exc.details else None,
                    last_diagnostic_at=now_utc().isoformat(),
                )
            else:
                outbound_message = ChannelMessageModel(
                    message_id=new_uuid(),
                    client_id=integration.client_id,
                    conversation_id=conversation.conversation_id,
                    channel_id=integration.channel_id,
                    direction="outbound",
                    external_sender_id=conversation.external_sender_id,
                    provider_event_id=str(send_result.get("provider_event_id", "")),
                    provider_status="accepted",
                    message_text=decision.reply_text,
                    content_summary=self._summarize_text(decision.reply_text),
                    raw_payload_json=send_result,
                    ai_metadata_json=decision_trace,
                    occurred_at=now_utc(),
                    outbound_status="sent",
                )
                session.add(outbound_message)
                conversation.last_message_at = outbound_message.occurred_at
                conversation.last_message_preview = outbound_message.content_summary
                conversation.status = "open"
                integration.last_outbound_at = outbound_message.occurred_at
                self._update_integration_diagnostics(
                    integration,
                    outbound_send_ok=True,
                    last_error_code=None,
                    last_error_message=None,
                    last_provider_status_code=200,
                    last_provider_response_excerpt=None,
                    last_diagnostic_at=now_utc().isoformat(),
                )
                for row in facts_pack.upsell_candidates[:MAX_UPSELL_MATCHES]:
                    session.add(
                        ChannelMessageProductMentionModel(
                            mention_id=new_uuid(),
                            client_id=integration.client_id,
                            message_id=outbound_message.message_id,
                            conversation_id=conversation.conversation_id,
                            product_id=row.product_id,
                            variant_id=row.variant_id,
                            mention_role="recommended",
                            unit_price_amount=row.unit_price,
                            min_price_amount=row.min_price,
                            available_to_sell_snapshot=row.available_to_sell,
                        )
                    )
                self._log_audit(
                    session,
                    client_id=integration.client_id,
                    actor_user_id=self._agent_user_id(session, integration.client_id),
                    entity_type="channel_message",
                    entity_id=outbound_message.message_id,
                    action="sales_agent_message_sent",
                    metadata_json={"conversation_id": conversation.conversation_id},
                )

        if order is not None:
            conversation.linked_draft_order_id = order.sales_order_id
            conversation.linked_draft_order_status = order.status
        if draft is not None:
            self._log_audit(
                session,
                client_id=integration.client_id,
                actor_user_id=self._agent_user_id(session, integration.client_id),
                entity_type="ai_review_draft",
                entity_id=draft.draft_id,
                action="sales_agent_draft_created",
                metadata_json={"conversation_id": conversation.conversation_id},
            )

    def _create_agent_order(
        self,
        session: Session,
        integration: ChannelIntegrationModel,
        conversation: ChannelConversationModel,
        customer: CustomerModel,
        location_id: str,
        order_line: dict[str, Any],
    ) -> SalesOrderModel:
        agent_user = self._ensure_agent_user(session, integration.client_id)
        order = self._sales_service._upsert_order(
            session,
            agent_user,
            sales_order_id=None,
            location_id=location_id,
            customer_id=str(customer.customer_id),
            customer_payload=None,
            payment_status="unpaid",
            shipment_status="pending",
            notes=f"Created by Sales Agent for conversation {conversation.conversation_id}",
            lines=[order_line],
            action="save_draft",
        )
        order.source_type = "sales_agent"
        order.source_channel_id = integration.channel_id
        order.source_conversation_id = conversation.conversation_id
        self._log_audit(
            session,
            client_id=integration.client_id,
            actor_user_id=agent_user.user_id,
            entity_type="sales_order",
            entity_id=order.sales_order_id,
            action="sales_agent_order_created",
            metadata_json={"conversation_id": conversation.conversation_id},
        )
        return order

    def _integration_by_webhook_key(self, session: Session, webhook_key: str) -> ChannelIntegrationModel:
        integration = session.execute(
            select(ChannelIntegrationModel).where(
                ChannelIntegrationModel.webhook_key == webhook_key,
                ChannelIntegrationModel.provider == "whatsapp",
            )
        ).scalar_one_or_none()
        self._require(integration is not None, message="Channel integration was not found", code="CHANNEL_NOT_FOUND", status_code=404)
        return integration

    def _target_client_id(self, user: AuthenticatedUser, target_client_id: str | None) -> str:
        candidate = self._clean_uuid(target_client_id)
        if candidate:
            if "SUPER_ADMIN" not in user.roles and candidate != user.client_id:
                raise ApiException(status_code=403, code="ACCESS_DENIED", message="Cross-tenant access is not allowed")
            return candidate
        resolved = self._clean_uuid(user.client_id)
        self._require(bool(resolved), message="Session client is invalid. Please log in again.", code="INVALID_SESSION", status_code=401)
        return resolved

    def _ensure_client_exists(self, session: Session, client_id: str) -> None:
        record = session.execute(
            select(ClientModel).where(ClientModel.client_id == client_id)
        ).scalar_one_or_none()
        self._require(record is not None, message="Client not found", code="CLIENT_NOT_FOUND", status_code=404)

    def _apply_status_update(self, session: Session, integration: ChannelIntegrationModel, status_payload: dict[str, Any]) -> int:
        provider_event_id = str(status_payload.get("id", "")).strip()
        if not provider_event_id:
            return 0
        message = session.execute(
            select(ChannelMessageModel).where(
                ChannelMessageModel.client_id == integration.client_id,
                ChannelMessageModel.provider_event_id == provider_event_id,
            )
        ).scalar_one_or_none()
        if message is None:
            return 0
        next_status = str(status_payload.get("status", "")).strip() or message.provider_status
        message.provider_status = next_status
        if next_status in {"sent", "delivered", "read"}:
            message.outbound_status = next_status
        return 1

    def _is_duplicate_provider_event_error(self, exc: IntegrityError) -> bool:
        message = str(getattr(exc, "orig", exc)).lower()
        return (
            "uq_channel_messages_client_provider_event" in message
            or (
                "duplicate key value violates unique constraint" in message
                and "provider_event" in message
                and "channel_messages" in message
            )
            or (
                "unique constraint failed" in message
                and "channel_messages.client_id" in message
                and "channel_messages.provider_event_id" in message
            )
        )

    def _iter_whatsapp_changes(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        entries = payload.get("entry") or []
        changes: list[dict[str, Any]] = []
        for entry in entries:
            for change in entry.get("changes") or []:
                changes.append(change)
        return changes

    def _verify_signature(self, integration: ChannelIntegrationModel, raw_body: bytes, signature: str | None) -> None:
        if not integration.app_secret.strip():
            raise ApiException(status_code=401, code="INVALID_SIGNATURE", message="App secret is required for webhook signature validation")
        if not signature or not signature.startswith("sha256="):
            raise ApiException(status_code=401, code="INVALID_SIGNATURE", message="Missing webhook signature")
        expected = hmac.new(
            integration.app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature.split("=", 1)[1], expected):
            raise ApiException(status_code=401, code="INVALID_SIGNATURE", message="Webhook signature mismatch")

    def _find_or_create_customer(
        self,
        session: Session,
        client_id: str,
        sender_id: str,
        profile_name: str,
    ) -> CustomerModel | None:
        normalized_phone = normalize_phone(sender_id)
        if not normalized_phone:
            return None
        customer = session.execute(
            select(CustomerModel).where(
                CustomerModel.client_id == client_id,
                CustomerModel.phone_normalized == normalized_phone,
            )
        ).scalar_one_or_none()
        if customer is not None:
            if not customer.whatsapp_number:
                customer.whatsapp_number = sender_id
            if profile_name and not customer.name:
                customer.name = profile_name
            return customer
        customer = CustomerModel(
            customer_id=new_uuid(),
            client_id=client_id,
            code=slugify_identifier(f"{profile_name or 'customer'}-{normalized_phone}", max_length=64, default="customer"),
            name=profile_name or f"Customer {normalized_phone[-4:]}",
            phone=sender_id,
            phone_normalized=normalized_phone,
            whatsapp_number=sender_id,
            email="",
            email_normalized="",
            status="active",
        )
        session.add(customer)
        session.flush()
        return customer

    def _find_or_create_conversation(
        self,
        session: Session,
        integration: ChannelIntegrationModel,
        customer: CustomerModel | None,
        sender_id: str,
    ) -> ChannelConversationModel:
        record = session.execute(
            select(ChannelConversationModel).where(
                ChannelConversationModel.channel_id == integration.channel_id,
                ChannelConversationModel.external_sender_id == sender_id,
            )
        ).scalar_one_or_none()
        if record is not None:
            if customer is not None:
                record.customer_id = customer.customer_id
            return record
        record = ChannelConversationModel(
            conversation_id=new_uuid(),
            client_id=integration.client_id,
            channel_id=integration.channel_id,
            customer_id=customer.customer_id if customer else None,
            external_sender_id=sender_id,
            external_sender_phone=sender_id,
            customer_name_snapshot=customer.name if customer else "",
            customer_phone_snapshot=customer.phone if customer else sender_id,
            customer_email_snapshot=customer.email if customer else "",
            status="open",
            last_message_preview="",
        )
        session.add(record)
        session.flush()
        return record

    def _refresh_customer_snapshot(self, session: Session, conversation: ChannelConversationModel) -> None:
        customer = None
        if conversation.customer_id:
            customer = session.execute(
                select(CustomerModel).where(
                    CustomerModel.client_id == conversation.client_id,
                    CustomerModel.customer_id == conversation.customer_id,
                )
            ).scalar_one_or_none()
        if customer is None:
            return
        conversation.customer_name_snapshot = customer.name
        conversation.customer_phone_snapshot = customer.phone or conversation.external_sender_phone
        conversation.customer_email_snapshot = customer.email
        total_spend, order_count, last_order_at = self._customer_order_snapshot(session, conversation.client_id, customer.customer_id)
        conversation.lifetime_spend_snapshot = total_spend
        conversation.lifetime_order_count_snapshot = order_count
        conversation.last_order_at_snapshot = last_order_at
        if order_count >= 5 or total_spend >= Decimal("1000"):
            conversation.customer_type_snapshot = "vip"
        elif order_count >= 1:
            conversation.customer_type_snapshot = "returning"
        else:
            conversation.customer_type_snapshot = "new"

    def _customer_order_snapshot(
        self,
        session: Session,
        client_id: str,
        customer_id: str,
    ) -> tuple[Decimal, int, Any]:
        row = session.execute(
            select(
                func.coalesce(func.sum(SalesOrderModel.total_amount), ZERO),
                func.count(SalesOrderModel.sales_order_id),
                func.max(SalesOrderModel.ordered_at),
            ).where(
                SalesOrderModel.client_id == client_id,
                SalesOrderModel.customer_id == customer_id,
                SalesOrderModel.status.in_(("confirmed", "completed")),
            )
        ).one()
        return as_decimal(row[0]), int(row[1] or 0), row[2]

    def _search_tokens(self, text: str) -> tuple[str, ...]:
        normalized = " ".join(text.strip().lower().split())
        raw_tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token]
        return tuple(
            token
            for token in raw_tokens
            if (
                token.isdigit()
                or token in SIZE_MATCH_TOKENS
                or (len(token) >= 3 and token not in MATCH_STOPWORDS)
            )
        )[:6]

    def _message_signals(self, text: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        lowered = text.strip().lower()
        normalized = re.sub(r"\s+", " ", lowered)
        reason_codes = {
            name
            for name, keywords in REVIEW_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        }
        is_greeting = any(keyword in normalized for keyword in GREETING_KEYWORDS)
        is_business_info = any(phrase in normalized for phrase in BUSINESS_INFO_PHRASES)
        if is_business_info:
            intent = "business_info"
        elif any(keyword in lowered for keyword in PURCHASE_KEYWORDS):
            intent = "purchase"
        elif any(keyword in lowered for keyword in PRICE_KEYWORDS):
            intent = "pricing"
        elif any(keyword in lowered for keyword in AVAILABILITY_KEYWORDS):
            intent = "availability"
        elif is_greeting and len(normalized.split()) <= 4:
            intent = "greeting"
        else:
            intent = "catalog"
        behavior_tags = tuple(
            sorted(
                tag
                for tag in {
                    "price_sensitive" if any(word in lowered for word in ("cheap", "budget", "best price", "lower")) else "",
                    "discount_seeking" if "discount" in lowered or "offer" in lowered else "",
                    "comparison_shopper" if any(word in lowered for word in ("other", "another", "compare", "alternative")) else "",
                    "upsell_receptive" if any(word in lowered for word in ("recommend", "also", "more")) else "",
                    "urgent_buyer" if any(word in lowered for word in ("today", "urgent", "now", "asap")) else "",
                }
                if tag
            )
        )
        return intent, behavior_tags, tuple(sorted(reason_codes))

    def _customer_snapshot(
        self,
        conversation: ChannelConversationModel,
        customer: CustomerModel | None,
    ) -> CustomerSnapshot:
        return CustomerSnapshot(
            customer_id=str(customer.customer_id) if customer else (str(conversation.customer_id) if conversation.customer_id else None),
            customer_name=conversation.customer_name_snapshot or (customer.name if customer else ""),
            customer_phone=conversation.customer_phone_snapshot or conversation.external_sender_phone,
            customer_type=conversation.customer_type_snapshot or "new",
            behavior_tags=tuple(sorted(conversation.behavior_tags_json or [])),
            lifetime_spend=as_decimal(conversation.lifetime_spend_snapshot),
            lifetime_order_count=int(conversation.lifetime_order_count_snapshot or 0),
            last_order_at=conversation.last_order_at_snapshot.isoformat() if conversation.last_order_at_snapshot else None,
        )

    def _conversation_memory_snapshot(self, session: Session, conversation_id: str) -> ConversationMemorySnapshot:
        rows = session.execute(
            select(ChannelMessageModel)
            .where(ChannelMessageModel.conversation_id == conversation_id)
            .order_by(ChannelMessageModel.occurred_at.desc(), ChannelMessageModel.created_at.desc())
            .limit(MAX_RECENT_TURNS)
        ).scalars().all()
        turns = tuple(
            ConversationTurn(
                speaker="customer" if row.direction == "inbound" else "sales_agent",
                text=self._bounded_text(row.message_text or row.content_summary, limit=160) or "",
            )
            for row in reversed(rows)
            if (row.message_text or row.content_summary)
        )
        summary_parts = [f"{turn.speaker}: {turn.text}" for turn in turns]
        summary = self._bounded_text(" | ".join(summary_parts), limit=FACTS_SUMMARY_LIMIT) or ""
        return ConversationMemorySnapshot(summary=summary, recent_turns=turns)

    def _match_variants(
        self,
        session: Session,
        client_id: str,
        location_id: str,
        text: str,
    ) -> list[MatchedVariant]:
        tokens = list(self._search_tokens(text))
        if not tokens:
            return []
        token_filters = []
        for token in tokens:
            pattern = f"%{token}%"
            token_filters.append(func.lower(ProductModel.brand).like(pattern))
            token_filters.append(func.lower(ProductModel.name).like(pattern))
            token_filters.append(func.lower(ProductVariantModel.title).like(pattern))
            token_filters.append(func.lower(ProductVariantModel.sku).like(pattern))
            token_filters.append(func.lower(ProductVariantModel.barcode).like(pattern))
        rows = session.execute(
            self._base_variant_stmt(client_id).where(or_(*token_filters))
        ).all()
        on_hand_map, reserved_map = self._stock_maps(session, client_id, location_id)
        ranked_items: list[tuple[MatchedVariant, int, int]] = []
        seen: set[str] = set()
        for product, variant, _supplier, _category in rows:
            if product.status != "active" or variant.status != "active":
                continue
            available = on_hand_map.get(str(variant.variant_id), ZERO) - reserved_map.get(str(variant.variant_id), ZERO)
            if available <= ZERO:
                continue
            unit_price = self._effective_variant_price(product, variant)
            if unit_price is None or unit_price <= ZERO:
                continue
            variant_key = str(variant.variant_id)
            if variant_key in seen:
                continue
            brand_value = (product.brand or "").lower()
            name_value = product.name.lower()
            title_value = variant.title.lower()
            sku_value = variant.sku.lower()
            barcode_value = variant.barcode.lower()
            brand_match_count = sum(1 for token in tokens if token in brand_value)
            name_match_count = sum(1 for token in tokens if token in name_value)
            title_match_count = sum(1 for token in tokens if token in title_value)
            sku_match_count = sum(1 for token in tokens if token in sku_value)
            barcode_match_count = sum(1 for token in tokens if token in barcode_value)
            match_score = (
                (brand_match_count * 8)
                + (name_match_count * 5)
                + (title_match_count * 4)
                + (sku_match_count * 3)
                + barcode_match_count
            )
            ranked_items.append(
                (
                    MatchedVariant(
                        variant_id=variant_key,
                        product_id=str(product.product_id),
                        product_name=product.name,
                        brand=product.brand or "",
                        label=build_variant_label(product.name, variant.title),
                        sku=variant.sku,
                        available_to_sell=available,
                        unit_price=as_decimal(unit_price),
                        min_price=as_optional_decimal(self._effective_variant_min_price(product, variant)),
                        match_score=match_score,
                    ),
                    brand_match_count,
                    title_match_count,
                )
            )
            seen.add(variant_key)
        if any(brand_matches > 0 for _item, brand_matches, _title_matches in ranked_items):
            ranked_items = [row for row in ranked_items if row[1] > 0]
        ranked_items.sort(
            key=lambda row: (
                row[0].match_score,
                row[1],
                row[2],
                row[0].available_to_sell,
                row[0].product_name,
            ),
            reverse=True,
        )
        return [item for item, _brand_matches, _title_matches in ranked_items[:5]]

    def _upsell_candidates(
        self,
        session: Session,
        client_id: str,
        location_id: str,
        exclude_variant_ids: set[str],
    ) -> list[MatchedVariant]:
        on_hand_map, reserved_map = self._stock_maps(session, client_id, location_id)
        sold_map = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    SalesOrderItemModel.variant_id,
                    func.coalesce(func.sum(SalesOrderItemModel.quantity_fulfilled), ZERO),
                )
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .where(
                    SalesOrderItemModel.client_id == client_id,
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.status == "completed",
                )
                .group_by(SalesOrderItemModel.variant_id)
            ).all()
        }
        items: list[MatchedVariant] = []
        for product, variant, _supplier, _category in session.execute(self._base_variant_stmt(client_id)).all():
            variant_id = str(variant.variant_id)
            if variant_id in exclude_variant_ids or product.status != "active" or variant.status != "active":
                continue
            available = on_hand_map.get(variant_id, ZERO) - reserved_map.get(variant_id, ZERO)
            if available <= ZERO:
                continue
            unit_price = self._effective_variant_price(product, variant)
            if unit_price is None or unit_price <= ZERO:
                continue
            sold_qty = sold_map.get(variant_id, ZERO)
            if sold_qty > Decimal("3"):
                continue
            items.append(
                MatchedVariant(
                    variant_id=variant_id,
                    product_id=str(product.product_id),
                    product_name=product.name,
                    brand=product.brand or "",
                    label=build_variant_label(product.name, variant.title),
                    sku=variant.sku,
                    available_to_sell=available,
                    unit_price=as_decimal(unit_price),
                    min_price=as_optional_decimal(self._effective_variant_min_price(product, variant)),
                    match_score=int((available * Decimal("10")) - sold_qty),
                )
            )
        items.sort(key=lambda item: (sold_map.get(item.variant_id, ZERO), -item.available_to_sell))
        return items[:MAX_UPSELL_MATCHES]

    def _should_use_helper(self, search_request: WarehouseSearchRequest, matches: list[MatchedVariant]) -> bool:
        if len(matches) <= 1:
            return False
        if self._query_brand_name(search_request, matches):
            return False
        if search_request.intent in {"purchase", "pricing"}:
            return True
        if len(search_request.tokens) <= 2:
            return True
        return len(matches) > 1 and matches[0].match_score <= matches[1].match_score + 1

    def _split_match_candidates(
        self,
        search_request: WarehouseSearchRequest,
        matches: list[MatchedVariant],
        helper_used: bool,
    ) -> tuple[tuple[MatchedVariant, ...], tuple[MatchedVariant, ...]]:
        if not matches:
            return (), ()
        if len(matches) == 1:
            return (matches[0],), ()
        if helper_used or search_request.intent in {"purchase", "pricing"}:
            if matches[0].match_score >= matches[1].match_score + 2:
                return (matches[0],), tuple(matches[1: 1 + MAX_ALTERNATIVE_MATCHES])
            return tuple(matches[:2]), tuple(matches[2: 2 + MAX_ALTERNATIVE_MATCHES])
        return tuple(matches[:MAX_PRIMARY_MATCHES]), tuple(matches[MAX_PRIMARY_MATCHES: MAX_PRIMARY_MATCHES + MAX_ALTERNATIVE_MATCHES])

    def _facts_reason_codes(
        self,
        *,
        search_request: WarehouseSearchRequest,
        primary_matches: tuple[MatchedVariant, ...],
        alternatives: tuple[MatchedVariant, ...],
        offer_policy: OfferPolicy,
    ) -> tuple[str, ...]:
        reason_codes = set(offer_policy.reason_codes)
        if not primary_matches and search_request.intent != "greeting":
            reason_codes.add("variant_match_failed")
        if len(primary_matches) > 1:
            reason_codes.add("ambiguous_variant")
        if primary_matches:
            lead = primary_matches[0]
            if search_request.quantity > lead.available_to_sell:
                reason_codes.add("out_of_stock")
            if search_request.intent in {"pricing", "purchase"} and lead.min_price is None and offer_policy.discount_requested:
                reason_codes.add("missing_price")
        if alternatives and search_request.intent == "catalog" and not primary_matches:
            reason_codes.add("low_confidence")
        return tuple(sorted(reason_codes))

    def _next_required_action(
        self,
        *,
        search_request: WarehouseSearchRequest,
        primary_matches: tuple[MatchedVariant, ...],
        reason_codes: tuple[str, ...],
        offer_policy: OfferPolicy,
    ) -> str:
        review_reasons = set(reason_codes).intersection(REPLY_REVIEW_REASONS)
        if search_request.intent in {"greeting", "business_info"} and not primary_matches:
            return "answer"
        if review_reasons:
            return "review"
        if not primary_matches:
            return "ask_clarifier"
        if len(primary_matches) > 1:
            return "ask_clarifier"
        lead = primary_matches[0]
        if search_request.intent == "purchase" and search_request.quantity <= lead.available_to_sell:
            return "create_draft_order"
        return "answer"

    def _client_business_name(self, session: Session, client_id: str) -> str | None:
        record = session.execute(
            select(ClientModel.business_name).where(ClientModel.client_id == client_id)
        ).scalar_one_or_none()
        return str(record).strip() if record else None

    def _query_brand_name(self, search_request: WarehouseSearchRequest, matches: list[MatchedVariant] | tuple[MatchedVariant, ...]) -> str | None:
        for token in search_request.tokens:
            for item in matches:
                brand = item.brand.strip()
                if brand and token in brand.lower():
                    return brand
        return None

    def _requested_color(self, normalized_text: str) -> str | None:
        for color in COLOR_TOKENS:
            if color in normalized_text:
                return color
        return None

    def _offer_unit_price(self, offer_policy: OfferPolicy) -> Decimal | None:
        return offer_policy.selected_unit_price or offer_policy.list_price

    def _quantize_decimal(self, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value.quantize(MONEY_QUANTUM)

    def _structured_openai_json(
        self,
        *,
        model_name: str,
        schema_name: str,
        schema: dict[str, Any],
        system_prompt: str,
        payload: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any] | None:
        if not settings.openai_api_key:
            return None
        request_payload = {
            "model": model_name,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(payload, default=str)}],
                },
            ],
            "store": False,
            "max_output_tokens": max(16, max_output_tokens),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        try:
            with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
                response = client.post(
                    f"{settings.openai_base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                )
            response.raise_for_status()
            body = response.json()
            output_text = str(body.get("output_text", "")).strip()
            return json.loads(output_text) if output_text else None
        except Exception:
            return None

    def _helper_rank_candidates_with_model(
        self,
        *,
        model_name: str,
        message_text: str,
        memory: ConversationMemorySnapshot,
        candidates: list[MatchedVariant],
    ) -> dict[str, Any] | None:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ranked_variant_ids": {"type": "array", "items": {"type": "string"}},
                "clarifier_options": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
            "required": ["ranked_variant_ids", "clarifier_options", "summary"],
        }
        payload = {
            "message_text": self._bounded_text(message_text, limit=180),
            "conversation_summary": memory.summary,
            "candidates": [self._matched_variant_payload(item) for item in candidates[: MAX_PRIMARY_MATCHES + MAX_ALTERNATIVE_MATCHES]],
        }
        return self._structured_openai_json(
            model_name=model_name,
            schema_name="warehouse_helper_rank",
            schema=schema,
            system_prompt=(
                "Rank already-filtered product variants for a warehouse-first sales agent. "
                "Use only the provided candidates. Do not invent stock or prices. "
                "Return concise clarifier options if more than one candidate is plausible."
            ),
            payload=payload,
            max_output_tokens=96,
        )

    def _deterministic_reply_from_facts(self, facts_pack: WarehouseFactsPack) -> SalesReplyDecision:
        reason_codes = set(facts_pack.reason_codes)
        quantity = facts_pack.search_request.quantity
        lead = facts_pack.primary_matches[0] if facts_pack.primary_matches else None
        selected_price = self._offer_unit_price(facts_pack.offer_policy)
        recommended_variant_ids = tuple(item.variant_id for item in facts_pack.upsell_candidates[:MAX_UPSELL_MATCHES])
        draft_order_request = None

        if facts_pack.intent == "business_info":
            return SalesReplyDecision(
                intent=facts_pack.intent,
                reply_text=(
                    f"You’re chatting with {facts_pack.business_name}. "
                    "If you want a product, send the name, size, or color and I’ll check stock for you."
                ),
                reply_mode="tier0_deterministic",
                confidence=Decimal("0.96"),
                selected_variant_id=None,
                selected_offer_id=facts_pack.offer_policy.selected_offer_id,
                recommended_variant_ids=(),
                needs_review=False,
                reason_codes=(),
                behavior_tags=facts_pack.behavior_tags,
                draft_order_request=None,
                helper_used=facts_pack.helper_used,
                sales_model_used=False,
            )

        if facts_pack.intent == "greeting" and lead is None:
            return SalesReplyDecision(
                intent=facts_pack.intent,
                reply_text=self._greeting_reply_text(facts_pack.conversation_memory),
                reply_mode="tier0_deterministic",
                confidence=Decimal("0.96"),
                selected_variant_id=None,
                selected_offer_id=facts_pack.offer_policy.selected_offer_id,
                recommended_variant_ids=(),
                needs_review=False,
                reason_codes=(),
                behavior_tags=facts_pack.behavior_tags,
                draft_order_request=None,
                helper_used=facts_pack.helper_used,
                sales_model_used=False,
            )

        if facts_pack.next_required_action == "review":
            reply = "I have the right context for this request. A team member needs to review it before I confirm anything, and they will follow up shortly."
            if lead is not None and "discount_request" in reason_codes and selected_price is not None:
                reply = f"{lead.label} is available. I need a quick approval before I confirm the final price for you."
            return SalesReplyDecision(
                intent=facts_pack.intent,
                reply_text=reply,
                reply_mode="review_hold",
                confidence=Decimal("0.62"),
                selected_variant_id=lead.variant_id if lead else None,
                selected_offer_id=facts_pack.offer_policy.selected_offer_id,
                recommended_variant_ids=recommended_variant_ids,
                needs_review=True,
                reason_codes=tuple(sorted(reason_codes)),
                behavior_tags=facts_pack.behavior_tags,
                draft_order_request=None,
                helper_used=facts_pack.helper_used,
                sales_model_used=False,
            )

        if facts_pack.next_required_action == "ask_clarifier":
            if lead is None:
                reply = "Send the product name, size, or color you want and I’ll check the exact variant for you."
            else:
                brand_name = self._query_brand_name(
                    facts_pack.search_request,
                    (*facts_pack.primary_matches, *facts_pack.alternatives),
                )
                if brand_name:
                    color = self._requested_color(facts_pack.search_request.normalized_text)
                    if color:
                        reply = f"I do have {brand_name} options in {color}. Tell me your size or preferred style and I’ll narrow it down."
                    else:
                        reply = f"I do have {brand_name} options. Tell me your size or preferred style and I’ll narrow it down."
                else:
                    options = facts_pack.clarifier_options or tuple(item.label for item in facts_pack.primary_matches[:2])
                    reply = f"I found two close matches: {', '.join(options[:2])}. Which one should I check for you?"
            return SalesReplyDecision(
                intent=facts_pack.intent,
                reply_text=reply,
                reply_mode="tier1_clarifier" if facts_pack.helper_used else "tier0_clarifier",
                confidence=Decimal("0.72") if lead is not None else Decimal("0.44"),
                selected_variant_id=lead.variant_id if lead else None,
                selected_offer_id=facts_pack.offer_policy.selected_offer_id,
                recommended_variant_ids=recommended_variant_ids,
                needs_review=False,
                reason_codes=tuple(sorted(reason_codes)),
                behavior_tags=facts_pack.behavior_tags,
                draft_order_request=None,
                helper_used=facts_pack.helper_used,
                sales_model_used=False,
            )

        if lead is None or selected_price is None:
            return SalesReplyDecision(
                intent=facts_pack.intent,
                reply_text="Tell me the product name, size, or color you want and I’ll check the best available option.",
                reply_mode="tier0_deterministic",
                confidence=Decimal("0.40"),
                selected_variant_id=None,
                selected_offer_id=facts_pack.offer_policy.selected_offer_id,
                recommended_variant_ids=(),
                needs_review=False,
                reason_codes=tuple(sorted(reason_codes | {"low_confidence"})),
                behavior_tags=facts_pack.behavior_tags,
                draft_order_request=None,
                helper_used=facts_pack.helper_used,
                sales_model_used=False,
            )

        if "out_of_stock" in reason_codes and quantity > lead.available_to_sell:
            reply = (
                f"I have {lead.available_to_sell:.0f} units of {lead.label} ready now, not {quantity:.0f}. "
                "If that quantity works, I can reserve it right away."
            )
            if facts_pack.alternatives:
                alt = facts_pack.alternatives[0]
                reply = f"{reply} The closest alternative is {alt.label} at {alt.unit_price:.2f}."
            return SalesReplyDecision(
                intent=facts_pack.intent,
                reply_text=reply,
                reply_mode="tier0_deterministic",
                confidence=Decimal("0.84"),
                selected_variant_id=lead.variant_id,
                selected_offer_id=facts_pack.offer_policy.selected_offer_id,
                recommended_variant_ids=recommended_variant_ids,
                needs_review=False,
                reason_codes=tuple(sorted(reason_codes)),
                behavior_tags=facts_pack.behavior_tags,
                draft_order_request=None,
                helper_used=facts_pack.helper_used,
                sales_model_used=False,
            )

        if facts_pack.next_required_action == "create_draft_order":
            draft_order_request = {
                "variant_id": lead.variant_id,
                "quantity": quantity,
                "unit_price": selected_price,
                "discount_amount": ZERO,
            }
            reply = (
                f"I can reserve {quantity:.0f} x {lead.label} at {selected_price:.2f} each. "
                "I’ve prepared the draft so we can confirm it quickly."
            )
            if facts_pack.upsell_candidates:
                upsell = facts_pack.upsell_candidates[0]
                reply = f"{reply} If you want an add-on, {upsell.label} is also ready at {upsell.unit_price:.2f}."
            return SalesReplyDecision(
                intent=facts_pack.intent,
                reply_text=reply,
                reply_mode="tier0_deterministic",
                confidence=Decimal("0.91"),
                selected_variant_id=lead.variant_id,
                selected_offer_id=facts_pack.offer_policy.selected_offer_id,
                recommended_variant_ids=recommended_variant_ids,
                needs_review=False,
                reason_codes=tuple(sorted(reason_codes)),
                behavior_tags=facts_pack.behavior_tags,
                draft_order_request=draft_order_request,
                helper_used=facts_pack.helper_used,
                sales_model_used=False,
            )

        reply = f"Yes, {lead.label} is available. Price is {selected_price:.2f} and I have {lead.available_to_sell:.0f} ready right now."
        if facts_pack.offer_policy.discount_requested and facts_pack.offer_policy.selected_offer_id != "list_price":
            reply = f"{lead.label} is available. The best instant price I can do is {selected_price:.2f} each, and I have {lead.available_to_sell:.0f} ready right now."
        if facts_pack.upsell_candidates and facts_pack.intent in {"catalog", "purchase"}:
            upsell = facts_pack.upsell_candidates[0]
            reply = f"{reply} If you want another option, {upsell.label} is also available at {upsell.unit_price:.2f}."
        return SalesReplyDecision(
            intent=facts_pack.intent,
            reply_text=reply,
            reply_mode="tier0_deterministic",
            confidence=Decimal("0.86"),
            selected_variant_id=lead.variant_id,
            selected_offer_id=facts_pack.offer_policy.selected_offer_id,
            recommended_variant_ids=recommended_variant_ids,
            needs_review=False,
            reason_codes=tuple(sorted(reason_codes)),
            behavior_tags=facts_pack.behavior_tags,
            draft_order_request=None,
            helper_used=facts_pack.helper_used,
            sales_model_used=False,
        )

    def _should_use_sales_model(self, facts_pack: WarehouseFactsPack, fallback: SalesReplyDecision) -> bool:
        if not settings.openai_api_key:
            return False
        if facts_pack.intent == "greeting":
            return False
        if fallback.needs_review and facts_pack.next_required_action == "review":
            return False
        if facts_pack.next_required_action == "ask_clarifier":
            return False
        if facts_pack.offer_policy.discount_requested:
            return True
        if facts_pack.next_required_action == "create_draft_order":
            return True
        if facts_pack.intent == "purchase" and facts_pack.upsell_candidates and len(facts_pack.primary_matches) == 1:
            return True
        if (
            {"comparison_shopper", "upsell_receptive"}.intersection(facts_pack.behavior_tags)
            and facts_pack.upsell_candidates
            and len(facts_pack.primary_matches) == 1
        ):
            return True
        return False

    def _sales_reply_with_model(
        self,
        *,
        model_name: str,
        facts_pack: WarehouseFactsPack,
        fallback: SalesReplyDecision,
    ) -> SalesReplyDecision:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "reply_text": {"type": "string"},
                "reply_mode": {"type": "string"},
                "selected_variant_id": {"type": ["string", "null"]},
                "selected_offer_id": {"type": ["string", "null"]},
                "recommended_variant_ids": {"type": "array", "items": {"type": "string"}},
                "needs_review": {"type": "boolean"},
                "reason_codes": {"type": "array", "items": {"type": "string"}},
                "behavior_tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "reply_text",
                "reply_mode",
                "selected_variant_id",
                "selected_offer_id",
                "recommended_variant_ids",
                "needs_review",
                "reason_codes",
                "behavior_tags",
            ],
        }
        payload = {
            "facts_pack": self._facts_pack_payload(facts_pack),
            "fallback": self._decision_payload(fallback),
        }
        parsed = self._structured_openai_json(
            model_name=model_name,
            schema_name="sales_reply_decision",
            schema=schema,
            system_prompt=(
                "You are the customer-facing sales agent. Speak like a concise human seller. "
                "Use only the provided facts pack. Never invent stock, warehouse scope, discounts, or prices. "
                "Choose only from the provided variant ids and offer ids. Push to close honestly."
            ),
            payload=payload,
            max_output_tokens=160,
        )
        if parsed is None:
            return fallback

        allowed_variant_ids = {item.variant_id for item in (*facts_pack.primary_matches, *facts_pack.alternatives)}
        allowed_offer_ids = {item.offer_id for item in facts_pack.offer_policy.auto_discount_steps}
        selected_variant_id = str(parsed.get("selected_variant_id") or "").strip() or fallback.selected_variant_id
        if selected_variant_id and selected_variant_id not in allowed_variant_ids:
            selected_variant_id = fallback.selected_variant_id
        selected_offer_id = str(parsed.get("selected_offer_id") or "").strip() or fallback.selected_offer_id
        if selected_offer_id and selected_offer_id not in allowed_offer_ids:
            selected_offer_id = fallback.selected_offer_id
        recommended_variant_ids = tuple(
            variant_id
            for variant_id in (
                str(item).strip()
                for item in parsed.get("recommended_variant_ids", [])
            )
            if variant_id in {row.variant_id for row in facts_pack.upsell_candidates}
        ) or fallback.recommended_variant_ids
        reason_codes = tuple(
            sorted(
                {
                    str(code).strip()
                    for code in parsed.get("reason_codes", [])
                    if str(code).strip()
                }
            )
        ) or fallback.reason_codes
        behavior_tags = tuple(
            sorted(
                {
                    str(tag).strip()
                    for tag in parsed.get("behavior_tags", [])
                    if str(tag).strip() in ALLOWED_BEHAVIOR_TAGS
                }
            )
        ) or fallback.behavior_tags
        return SalesReplyDecision(
            intent=facts_pack.intent,
            reply_text=str(parsed.get("reply_text", "")).strip() or fallback.reply_text,
            reply_mode=str(parsed.get("reply_mode", "")).strip() or "tier2_sales_model",
            confidence=Decimal("0.88"),
            selected_variant_id=selected_variant_id,
            selected_offer_id=selected_offer_id,
            recommended_variant_ids=recommended_variant_ids,
            needs_review=bool(parsed.get("needs_review")) or bool(set(reason_codes).intersection(REPLY_REVIEW_REASONS)),
            reason_codes=reason_codes,
            behavior_tags=behavior_tags,
            draft_order_request=fallback.draft_order_request,
            helper_used=facts_pack.helper_used,
            sales_model_used=True,
        )

    def _send_whatsapp_text(self, integration: ChannelIntegrationModel, recipient: str, text: str) -> dict[str, Any]:
        if not integration.access_token or not integration.phone_number_id:
            raise ApiException(status_code=400, code="CHANNEL_NOT_READY", message="WhatsApp channel is not ready to send messages")
        with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
            response = client.post(
                f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{integration.phone_number_id}/messages",
                headers={
                    "Authorization": f"Bearer {integration.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"preview_url": False, "body": text},
                },
            )
        if response.status_code >= 400:
            raise ApiException(
                status_code=502,
                code="WHATSAPP_SEND_FAILED",
                message=response.text or "WhatsApp send failed",
                details={
                    "provider_status_code": response.status_code,
                    "provider_response_excerpt": self._bounded_text(response.text, limit=400),
                },
            )
        body = response.json()
        message_id = ""
        messages = body.get("messages") or []
        if messages:
            message_id = str(messages[0].get("id", "")).strip()
        return {
            "provider": "whatsapp",
            "provider_event_id": message_id,
            "response": body,
        }

    def _greeting_reply_text(self, memory: ConversationMemorySnapshot) -> str:
        if any(turn.speaker == "sales_agent" for turn in memory.recent_turns):
            return "Send the product name, size, or color you want and I’ll check the live stock and price for you."
        return "Hi. Tell me the product name, size, or color you want and I’ll check the live stock and price for you."

    def _probe_whatsapp_graph(
        self,
        *,
        external_account_id: str,
        phone_number_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        if not access_token or not phone_number_id:
            return {
                "ok": False,
                "error_code": "graph_auth_failed",
                "error_message": "WhatsApp access token and phone number ID are required.",
                "provider_status_code": None,
                "provider_response_excerpt": None,
                "provider_details": {},
            }
        headers = {"Authorization": f"Bearer {access_token}"}
        provider_details: dict[str, Any] = {}
        with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
            response = client.get(
                f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{phone_number_id}",
                headers=headers,
                params={"fields": "id,display_phone_number,verified_name"},
            )
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "error_code": "graph_auth_failed",
                    "error_message": response.text or "Unable to validate WhatsApp credentials.",
                    "provider_status_code": response.status_code,
                    "provider_response_excerpt": self._bounded_text(response.text, limit=400),
                    "provider_details": provider_details,
                }
            phone_details = response.json()
            provider_details.update(
                {
                    "display_phone_number": str(phone_details.get("display_phone_number", "")).strip(),
                    "verified_name": str(phone_details.get("verified_name", "")).strip(),
                    "resolved_phone_number_id": str(phone_details.get("id", "")).strip(),
                }
            )
            if external_account_id:
                account_response = client.get(
                    f"https://graph.facebook.com/{settings.whatsapp_graph_version}/{external_account_id}/phone_numbers",
                    headers=headers,
                )
                if account_response.status_code >= 400:
                    return {
                        "ok": False,
                        "error_code": "graph_auth_failed",
                        "error_message": account_response.text or "Unable to read WhatsApp business account phone numbers.",
                        "provider_status_code": account_response.status_code,
                        "provider_response_excerpt": self._bounded_text(account_response.text, limit=400),
                        "provider_details": provider_details,
                    }
                phone_rows = account_response.json().get("data") or []
                provider_details["business_phone_count"] = len(phone_rows)
                if not any(str(item.get("id", "")).strip() == phone_number_id for item in phone_rows):
                    return {
                        "ok": False,
                        "error_code": "graph_auth_failed",
                        "error_message": "The phone number ID is not linked to the configured WhatsApp business account.",
                        "provider_status_code": 400,
                        "provider_response_excerpt": "Configured phone_number_id was not found in the WABA phone number list.",
                        "provider_details": provider_details,
                    }
        return {
            "ok": True,
            "error_code": None,
            "error_message": None,
            "provider_status_code": 200,
            "provider_response_excerpt": None,
            "provider_details": provider_details,
        }

    def _probe_openai_model(self, *, model_name: str) -> dict[str, Any]:
        if not settings.openai_api_key:
            return {
                "ok": False,
                "error_code": "openai_not_configured",
                "error_message": "OPENAI_API_KEY is not configured on the backend.",
                "provider_status_code": None,
                "provider_response_excerpt": None,
            }
        request_payload = {
            "model": model_name,
            "input": "Reply with OK only.",
            "store": False,
            "max_output_tokens": 16,
        }
        try:
            with httpx.Client(timeout=settings.openai_timeout_seconds) as client:
                response = client.post(
                    f"{settings.openai_base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                )
        except Exception as exc:
            return {
                "ok": False,
                "error_code": "openai_probe_failed",
                "error_message": str(exc),
                "provider_status_code": None,
                "provider_response_excerpt": None,
            }
        if response.status_code >= 400:
            return {
                "ok": False,
                "error_code": "openai_probe_failed",
                "error_message": response.text or "OpenAI probe failed.",
                "provider_status_code": response.status_code,
                "provider_response_excerpt": self._bounded_text(response.text, limit=400),
            }
        return {
            "ok": True,
            "error_code": None,
            "error_message": None,
            "provider_status_code": 200,
            "provider_response_excerpt": None,
        }

    def _run_whatsapp_diagnostics(
        self,
        session: Session,
        *,
        integration: ChannelIntegrationModel | None,
        client_id: str,
        external_account_id: str,
        phone_number_id: str,
        verify_token_set: bool,
        access_token: str,
        app_secret: str,
        model_name: str,
        default_location_id: str | None,
        auto_send_enabled: bool,
        persist: bool,
    ) -> dict[str, Any]:
        diagnostics_time = now_utc().isoformat()
        provider_details: dict[str, Any] = {}
        failures: list[dict[str, Any]] = []

        if default_location_id:
            location = session.execute(
                select(LocationModel).where(
                    LocationModel.client_id == client_id,
                    LocationModel.location_id == default_location_id,
                    LocationModel.status == "active",
                )
            ).scalar_one_or_none()
            if location is None:
                failures.append(
                    {
                        "error_code": "location_missing",
                        "error_message": "The configured default location is missing or inactive.",
                        "provider_status_code": None,
                        "provider_response_excerpt": None,
                    }
                )
        else:
            try:
                self._default_location_id(session, client_id)
            except ApiException as exc:
                failures.append(
                    {
                        "error_code": self._diagnostic_code(exc),
                        "error_message": exc.message,
                        "provider_status_code": None,
                        "provider_response_excerpt": None,
                    }
                )

        graph_probe = self._probe_whatsapp_graph(
            external_account_id=external_account_id,
            phone_number_id=phone_number_id,
            access_token=access_token,
        )
        provider_details.update(graph_probe.get("provider_details", {}))
        if not graph_probe["ok"]:
            failures.append(graph_probe)

        openai_probe = self._probe_openai_model(model_name=model_name)
        if not openai_probe["ok"]:
            failures.append(openai_probe)

        primary_failure = failures[0] if failures else {}
        diagnostics_payload = self._diagnostics_payload(
            config_saved=bool(phone_number_id and verify_token_set and access_token and app_secret),
            verify_token_set=verify_token_set,
            webhook_verified_at=self._integration_diagnostics(integration).get("webhook_verified_at") if integration else None,
            last_webhook_post_at=self._integration_diagnostics(integration).get("last_webhook_post_at") if integration else None,
            signature_validation_ok=self._integration_diagnostics(integration).get("signature_validation_ok") if integration else None,
            graph_auth_ok=graph_probe["ok"],
            outbound_send_ok=self._integration_diagnostics(integration).get("outbound_send_ok") if integration else None,
            openai_ready=bool(settings.openai_api_key),
            openai_probe_ok=openai_probe["ok"],
            last_error_code=primary_failure.get("error_code"),
            last_error_message=primary_failure.get("error_message"),
            last_provider_status_code=primary_failure.get("provider_status_code"),
            last_provider_response_excerpt=primary_failure.get("provider_response_excerpt"),
            last_diagnostic_at=diagnostics_time,
            auto_send_enabled=auto_send_enabled,
        )
        if persist and integration is not None:
            self._update_integration_diagnostics(
                integration,
                graph_auth_ok=graph_probe["ok"],
                openai_probe_ok=openai_probe["ok"],
                last_error_code=diagnostics_payload["last_error_code"],
                last_error_message=diagnostics_payload["last_error_message"],
                last_provider_status_code=diagnostics_payload["last_provider_status_code"],
                last_provider_response_excerpt=diagnostics_payload["last_provider_response_excerpt"],
                last_diagnostic_at=diagnostics_time,
            )
        return {
            "diagnostics": diagnostics_payload,
            "provider_details": provider_details,
        }

    def _default_location_id(self, session: Session, client_id: str) -> str:
        location = session.execute(
            select(LocationModel)
            .where(LocationModel.client_id == client_id, LocationModel.status == "active")
            .order_by(LocationModel.is_default.desc(), LocationModel.name.asc())
        ).scalar_one_or_none()
        self._require(location is not None, message="No active location is configured for this tenant", code="LOCATION_REQUIRED")
        return str(location.location_id)

    def _profile_for_client(self, session: Session, client_id: str) -> TenantAgentProfileModel | None:
        return session.execute(
            select(TenantAgentProfileModel).where(TenantAgentProfileModel.client_id == client_id)
        ).scalar_one_or_none()

    def _latest_draft(self, session: Session, conversation_id: str) -> AiReviewDraftModel | None:
        return session.execute(
            select(AiReviewDraftModel)
            .where(AiReviewDraftModel.conversation_id == conversation_id)
            .order_by(AiReviewDraftModel.created_at.desc())
        ).scalars().first()

    def _linked_order_payload(self, session: Session, sales_order_id: str | None) -> dict[str, Any] | None:
        if not sales_order_id:
            return None
        order = session.execute(
            select(SalesOrderModel).where(SalesOrderModel.sales_order_id == sales_order_id)
        ).scalar_one_or_none()
        if order is None:
            return None
        return self._sales_service._sales_order_payload(session, order)

    def _message_mentions_payload(self, session: Session, message_id: str) -> list[dict[str, Any]]:
        return [
            {
                "mention_id": str(item.mention_id),
                "product_id": str(item.product_id) if item.product_id else None,
                "variant_id": str(item.variant_id) if item.variant_id else None,
                "mention_role": item.mention_role,
                "quantity": as_decimal(item.quantity) if item.quantity is not None else None,
                "unit_price": as_optional_decimal(item.unit_price_amount),
                "min_price": as_optional_decimal(item.min_price_amount),
                "available_to_sell": as_decimal(item.available_to_sell_snapshot) if item.available_to_sell_snapshot is not None else None,
            }
            for item in session.execute(
                select(ChannelMessageProductMentionModel)
                .where(ChannelMessageProductMentionModel.message_id == message_id)
                .order_by(ChannelMessageProductMentionModel.created_at.asc())
            ).scalars()
        ]

    def _channel_for_owner_or_admin(
        self,
        session: Session,
        user: AuthenticatedUser,
        channel_id: str,
    ) -> tuple[ChannelIntegrationModel, TenantAgentProfileModel | None]:
        self._require_owner_or_admin(user)
        integration = session.execute(
            select(ChannelIntegrationModel).where(ChannelIntegrationModel.channel_id == channel_id)
        ).scalar_one_or_none()
        self._require(integration is not None, message="Channel not found", code="CHANNEL_NOT_FOUND", status_code=404)
        if "SUPER_ADMIN" not in user.roles and integration.client_id != user.client_id:
            raise ApiException(status_code=403, code="ACCESS_DENIED", message="Cross-tenant access is not allowed")
        return integration, self._profile_for_client(session, integration.client_id)

    def _integration_base_config(self, integration: ChannelIntegrationModel) -> dict[str, Any]:
        config = dict(integration.config_json or {})
        config.pop("diagnostics", None)
        return config

    def _integration_diagnostics(self, integration: ChannelIntegrationModel) -> dict[str, Any]:
        config = dict(integration.config_json or {})
        diagnostics = config.get("diagnostics") if isinstance(config.get("diagnostics"), dict) else {}
        return dict(diagnostics or {})

    def _set_integration_config(
        self,
        integration: ChannelIntegrationModel,
        *,
        model_name: str | None = None,
        persona_prompt: str | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        config = self._integration_base_config(integration)
        if model_name is not None:
            config["model_name"] = model_name
        if persona_prompt is not None:
            config["persona_prompt"] = persona_prompt
        if diagnostics is None:
            diagnostics = self._integration_diagnostics(integration)
        config["diagnostics"] = diagnostics
        integration.config_json = config

    def _reset_integration_diagnostics(
        self,
        integration: ChannelIntegrationModel,
        *,
        reset_webhook: bool = False,
        reset_provider: bool = False,
        reset_openai: bool = False,
    ) -> None:
        diagnostics = self._integration_diagnostics(integration)
        if reset_webhook:
            diagnostics["webhook_verified_at"] = None
            diagnostics["last_webhook_post_at"] = None
            diagnostics["signature_validation_ok"] = None
        if reset_provider:
            diagnostics["graph_auth_ok"] = None
            diagnostics["outbound_send_ok"] = None
            diagnostics["last_provider_status_code"] = None
            diagnostics["last_provider_response_excerpt"] = None
        if reset_openai:
            diagnostics["openai_probe_ok"] = None
        diagnostics["last_error_code"] = None
        diagnostics["last_error_message"] = None
        diagnostics["last_diagnostic_at"] = None
        self._set_integration_config(integration, diagnostics=diagnostics)

    def _update_integration_diagnostics(self, integration: ChannelIntegrationModel, **updates: Any) -> dict[str, Any]:
        diagnostics = self._integration_diagnostics(integration)
        for key, value in updates.items():
            diagnostics[key] = value
        self._set_integration_config(integration, diagnostics=diagnostics)
        return diagnostics

    def _diagnostic_timestamp(self, value: Any) -> str | None:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        raw = str(value or "").strip()
        return raw or None

    def _bounded_text(self, text: Any, *, limit: int = 280) -> str | None:
        compact = " ".join(str(text or "").split())
        if not compact:
            return None
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

    def _diagnostic_code(self, exc: Exception) -> str:
        if isinstance(exc, ApiException):
            mapping = {
                "INVALID_SIGNATURE": "invalid_signature",
                "WHATSAPP_SEND_FAILED": "whatsapp_send_failed",
                "CHANNEL_NOT_READY": "graph_auth_failed",
                "LOCATION_REQUIRED": "location_missing",
                "CONVERSATION_NOT_FOUND": "conversation_not_found",
            }
            return mapping.get(exc.code, exc.code.lower())
        return "unexpected_error"

    def _integration_diagnostics_payload(self, integration: ChannelIntegrationModel) -> dict[str, Any]:
        diagnostics = self._integration_diagnostics(integration)
        return self._diagnostics_payload(
            config_saved=bool(
                integration.phone_number_id
                and integration.verify_token_hash
                and integration.access_token
                and integration.app_secret
            ),
            verify_token_set=bool(integration.verify_token_hash),
            webhook_verified_at=diagnostics.get("webhook_verified_at"),
            last_webhook_post_at=diagnostics.get("last_webhook_post_at"),
            signature_validation_ok=diagnostics.get("signature_validation_ok"),
            graph_auth_ok=diagnostics.get("graph_auth_ok"),
            outbound_send_ok=diagnostics.get("outbound_send_ok"),
            openai_ready=bool(settings.openai_api_key),
            openai_probe_ok=diagnostics.get("openai_probe_ok"),
            last_error_code=diagnostics.get("last_error_code"),
            last_error_message=diagnostics.get("last_error_message"),
            last_provider_status_code=diagnostics.get("last_provider_status_code"),
            last_provider_response_excerpt=diagnostics.get("last_provider_response_excerpt"),
            last_diagnostic_at=diagnostics.get("last_diagnostic_at"),
            auto_send_enabled=integration.auto_send_enabled,
        )

    def _diagnostics_payload(
        self,
        *,
        config_saved: bool,
        verify_token_set: bool,
        webhook_verified_at: Any,
        last_webhook_post_at: Any,
        signature_validation_ok: bool | None,
        graph_auth_ok: bool | None,
        outbound_send_ok: bool | None,
        openai_ready: bool,
        openai_probe_ok: bool | None,
        last_error_code: Any,
        last_error_message: Any,
        last_provider_status_code: Any,
        last_provider_response_excerpt: Any,
        last_diagnostic_at: Any,
        auto_send_enabled: bool,
    ) -> dict[str, Any]:
        payload = {
            "config_saved": config_saved,
            "verify_token_set": verify_token_set,
            "webhook_verified_at": self._diagnostic_timestamp(webhook_verified_at),
            "last_webhook_post_at": self._diagnostic_timestamp(last_webhook_post_at),
            "signature_validation_ok": signature_validation_ok,
            "graph_auth_ok": graph_auth_ok,
            "outbound_send_ok": outbound_send_ok,
            "openai_ready": openai_ready,
            "openai_probe_ok": openai_probe_ok,
            "last_error_code": str(last_error_code or "").strip() or None,
            "last_error_message": str(last_error_message or "").strip() or None,
            "last_provider_status_code": last_provider_status_code,
            "last_provider_response_excerpt": self._bounded_text(last_provider_response_excerpt),
            "last_diagnostic_at": self._diagnostic_timestamp(last_diagnostic_at),
        }
        payload["next_action"] = self._integration_next_action(payload, auto_send_enabled=auto_send_enabled)
        return payload

    def _integration_next_action(self, payload: dict[str, Any], *, auto_send_enabled: bool) -> str:
        if not payload.get("config_saved"):
            return "Save the WhatsApp phone number ID, verify token, access token, and app secret for this tenant."
        if not payload.get("webhook_verified_at"):
            return "Verify the callback URL in Meta with the exact verify token saved for this tenant."
        if payload.get("signature_validation_ok") is False:
            return "Re-save the exact Meta app secret for this app, then send a new WhatsApp test message."
        if not payload.get("last_webhook_post_at"):
            return "Subscribe the Meta app to the messages webhook field, then send a new WhatsApp test message."
        if payload.get("graph_auth_ok") is False:
            return "Run diagnostics and correct the Meta access token, phone number ID, or business account mapping."
        if payload.get("outbound_send_ok") is False:
            return "Run a smoke send and review the saved provider error before enabling live customer traffic."
        if not payload.get("openai_ready"):
            return "Set OPENAI_API_KEY on the backend environment and restart the API service."
        if payload.get("openai_probe_ok") is False:
            return "Fix the backend OpenAI key or model configuration, then rerun diagnostics."
        if not auto_send_enabled:
            return "Turn on guarded auto-send after diagnostics are passing."
        return "Channel is ready. Send a WhatsApp test message and confirm the conversation appears in Sales Agent."

    def _integration_payload(
        self,
        integration: ChannelIntegrationModel,
        profile: TenantAgentProfileModel | None,
    ) -> dict[str, Any]:
        config = self._integration_base_config(integration)
        diagnostics = self._integration_diagnostics_payload(integration)
        return {
            "channel_id": str(integration.channel_id),
            "provider": integration.provider,
            "display_name": integration.display_name,
            "status": integration.status,
            "webhook_key": integration.webhook_key,
            "external_account_id": integration.external_account_id,
            "phone_number_id": integration.phone_number_id,
            "phone_number": integration.phone_number,
            "verify_token_set": bool(integration.verify_token_hash),
            "inbound_secret_set": bool(integration.app_secret),
            "access_token_set": bool(integration.access_token),
            "default_location_id": str(integration.default_location_id) if integration.default_location_id else None,
            "auto_send_enabled": integration.auto_send_enabled,
            "agent_enabled": profile.is_enabled if profile else False,
            "model_name": str(config.get("model_name", profile.model_name if profile else settings.openai_model)),
            "persona_prompt": str(config.get("persona_prompt", profile.persona_prompt if profile else "")),
            "config": {key: value for key, value in config.items() if isinstance(value, str)},
            "created_at": integration.created_at.isoformat(),
            "updated_at": integration.updated_at.isoformat(),
            "last_inbound_at": integration.last_inbound_at.isoformat() if integration.last_inbound_at else None,
            "last_outbound_at": integration.last_outbound_at.isoformat() if integration.last_outbound_at else None,
            **diagnostics,
        }

    def _conversation_summary_payload(
        self,
        record: ChannelConversationModel,
        latest_draft: AiReviewDraftModel | None,
        linked_order: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata = dict(record.metadata_json or {})
        return {
            "conversation_id": str(record.conversation_id),
            "channel_id": str(record.channel_id),
            "customer_id": str(record.customer_id) if record.customer_id else None,
            "customer_name": record.customer_name_snapshot,
            "customer_phone": record.customer_phone_snapshot or record.external_sender_phone,
            "customer_email": record.customer_email_snapshot,
            "external_sender_id": record.external_sender_id,
            "status": record.status,
            "customer_type": record.customer_type_snapshot,
            "behavior_tags": list(record.behavior_tags_json or []),
            "lifetime_spend": as_decimal(record.lifetime_spend_snapshot),
            "lifetime_order_count": int(record.lifetime_order_count_snapshot or 0),
            "latest_intent": record.latest_intent,
            "latest_summary": record.latest_summary,
            "last_message_preview": record.last_message_preview,
            "last_message_at": record.last_message_at.isoformat() if record.last_message_at else None,
            "latest_recommended_products_summary": record.last_recommended_products_summary,
            "linked_draft_order_id": str(record.linked_draft_order_id) if record.linked_draft_order_id else None,
            "linked_draft_order_status": record.linked_draft_order_status,
            "latest_draft_id": str(latest_draft.draft_id) if latest_draft else None,
            "latest_draft_status": latest_draft.status if latest_draft else None,
            "latest_trace": metadata.get("latest_trace") if isinstance(metadata.get("latest_trace"), dict) else {},
            "linked_order": linked_order,
        }

    def _draft_payload(self, draft: AiReviewDraftModel) -> dict[str, Any]:
        return {
            "draft_id": str(draft.draft_id),
            "conversation_id": str(draft.conversation_id),
            "linked_sales_order_id": str(draft.linked_sales_order_id) if draft.linked_sales_order_id else None,
            "status": draft.status,
            "ai_draft_text": draft.ai_draft_text,
            "edited_text": draft.edited_text,
            "final_text": draft.final_text,
            "intent": draft.intent,
            "confidence": as_optional_decimal(draft.confidence),
            "grounding": draft.grounding_json or {},
            "reason_codes": list(draft.reason_codes_json or []),
            "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
            "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
            "failed_reason": draft.failed_reason,
            "human_modified": draft.human_modified,
        }

    def _matched_variant_payload(self, item: MatchedVariant) -> dict[str, Any]:
        return {
            "variant_id": item.variant_id,
            "product_id": item.product_id,
            "product_name": item.product_name,
            "brand": item.brand,
            "label": item.label,
            "sku": item.sku,
            "available_to_sell": str(item.available_to_sell),
            "unit_price": str(item.unit_price),
            "min_price": str(item.min_price) if item.min_price is not None else None,
        }

    def _offer_band_payload(self, item: OfferBand) -> dict[str, Any]:
        return {
            "offer_id": item.offer_id,
            "label": item.label,
            "unit_price": str(item.unit_price),
            "discount_percent": str(item.discount_percent),
            "requires_review": item.requires_review,
        }

    def _offer_policy_payload(self, policy: OfferPolicy) -> dict[str, Any]:
        return {
            "list_price": str(policy.list_price) if policy.list_price is not None else None,
            "floor_price": str(policy.floor_price) if policy.floor_price is not None else None,
            "preferred_close_price": str(policy.preferred_close_price) if policy.preferred_close_price is not None else None,
            "selected_offer_id": policy.selected_offer_id,
            "selected_unit_price": str(policy.selected_unit_price) if policy.selected_unit_price is not None else None,
            "requires_discount_approval": policy.requires_discount_approval,
            "discount_requested": policy.discount_requested,
            "auto_discount_steps": [self._offer_band_payload(item) for item in policy.auto_discount_steps],
            "reason_codes": list(policy.reason_codes),
        }

    def _customer_snapshot_payload(self, snapshot: CustomerSnapshot) -> dict[str, Any]:
        return {
            "customer_id": snapshot.customer_id,
            "customer_name": snapshot.customer_name,
            "customer_phone": snapshot.customer_phone,
            "customer_type": snapshot.customer_type,
            "behavior_tags": list(snapshot.behavior_tags),
            "lifetime_spend": str(snapshot.lifetime_spend),
            "lifetime_order_count": snapshot.lifetime_order_count,
            "last_order_at": snapshot.last_order_at,
        }

    def _conversation_memory_payload(self, snapshot: ConversationMemorySnapshot) -> dict[str, Any]:
        return {
            "summary": snapshot.summary,
            "recent_turns": [
                {"speaker": item.speaker, "text": item.text}
                for item in snapshot.recent_turns
            ],
        }

    def _facts_pack_payload(self, facts_pack: WarehouseFactsPack) -> dict[str, Any]:
        return {
            "intent": facts_pack.intent,
            "business_name": facts_pack.business_name,
            "search_request": {
                "client_id": facts_pack.search_request.client_id,
                "location_id": facts_pack.search_request.location_id,
                "message_text": self._bounded_text(facts_pack.search_request.message_text, limit=180),
                "normalized_text": facts_pack.search_request.normalized_text,
                "tokens": list(facts_pack.search_request.tokens),
                "intent": facts_pack.search_request.intent,
                "quantity": str(facts_pack.search_request.quantity),
            },
            "customer_snapshot": self._customer_snapshot_payload(facts_pack.customer_snapshot),
            "conversation_memory": self._conversation_memory_payload(facts_pack.conversation_memory),
            "primary_matches": [self._matched_variant_payload(item) for item in facts_pack.primary_matches[:MAX_PRIMARY_MATCHES]],
            "alternatives": [self._matched_variant_payload(item) for item in facts_pack.alternatives[:MAX_ALTERNATIVE_MATCHES]],
            "upsell_candidates": [self._matched_variant_payload(item) for item in facts_pack.upsell_candidates[:MAX_UPSELL_MATCHES]],
            "offer_policy": self._offer_policy_payload(facts_pack.offer_policy),
            "stock_scope": facts_pack.stock_scope,
            "next_required_action": facts_pack.next_required_action,
            "helper_used": facts_pack.helper_used,
            "helper_summary": facts_pack.helper_summary,
            "clarifier_options": list(facts_pack.clarifier_options),
            "behavior_tags": list(facts_pack.behavior_tags),
            "reason_codes": list(facts_pack.reason_codes),
        }

    def _decision_payload(self, decision: SalesReplyDecision) -> dict[str, Any]:
        return {
            "intent": decision.intent,
            "reply_text": decision.reply_text,
            "reply_mode": decision.reply_mode,
            "confidence": str(decision.confidence),
            "selected_variant_id": decision.selected_variant_id,
            "selected_offer_id": decision.selected_offer_id,
            "recommended_variant_ids": list(decision.recommended_variant_ids),
            "needs_review": decision.needs_review,
            "reason_codes": list(decision.reason_codes),
            "behavior_tags": list(decision.behavior_tags),
            "draft_order_request": {
                key: (str(value) if isinstance(value, Decimal) else value)
                for key, value in (decision.draft_order_request or {}).items()
            },
            "helper_used": decision.helper_used,
            "sales_model_used": decision.sales_model_used,
        }

    def _decision_trace_payload(self, facts_pack: WarehouseFactsPack, decision: SalesReplyDecision) -> dict[str, Any]:
        return {
            "runtime": {
                "tier": decision.reply_mode,
                "helper_used": facts_pack.helper_used,
                "sales_model_used": decision.sales_model_used,
                "next_required_action": facts_pack.next_required_action,
                "stock_scope": facts_pack.stock_scope,
            },
            "facts_pack": self._facts_pack_payload(facts_pack),
            "decision": self._decision_payload(decision),
        }

    def _recommended_summary(self, matches: list[MatchedVariant], upsell_options: list[MatchedVariant]) -> str:
        names = [item.label for item in matches[:2]] + [item.label for item in upsell_options[:2]]
        seen: list[str] = []
        for name in names:
            if name and name not in seen:
                seen.append(name)
        return ", ".join(seen[:3])

    def _extract_quantity(self, text: str) -> Decimal:
        match = re.search(r"\b(\d{1,3})\b", text)
        if not match:
            return Decimal("1")
        return Decimal(match.group(1))

    def _rolling_summary(
        self,
        *,
        memory: ConversationMemorySnapshot,
        inbound_text: str,
        latest_reply: str,
        needs_review: bool,
    ) -> str:
        parts = []
        if memory.summary:
            parts.append(memory.summary)
        if inbound_text.strip():
            parts.append(f"customer: {self._summarize_text(inbound_text, limit=180)}")
        if latest_reply.strip():
            prefix = "review" if needs_review else "agent"
            parts.append(f"{prefix}: {self._summarize_text(latest_reply, limit=220)}")
        return self._bounded_text(" | ".join(parts), limit=FACTS_SUMMARY_LIMIT) or ""

    def _summarize_text(self, text: str, *, limit: int = 280) -> str:
        compact = " ".join(text.strip().split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

    def _conversation_for_update(self, session: Session, client_id: str, conversation_id: str) -> ChannelConversationModel:
        record = session.execute(
            select(ChannelConversationModel).where(
                ChannelConversationModel.client_id == client_id,
                ChannelConversationModel.conversation_id == conversation_id,
            )
        ).scalar_one_or_none()
        self._require(record is not None, message="Conversation not found", code="CONVERSATION_NOT_FOUND", status_code=404)
        return record

    def _agent_user_id(self, session: Session, client_id: str) -> str:
        return self._ensure_agent_user(session, client_id).user_id

    def _canonical_actor_user_id(self, session: Session, user: AuthenticatedUser, client_id: str) -> str | None:
        direct_user_id = self._clean_uuid(user.user_id)
        if direct_user_id:
            return direct_user_id
        email = user.email.lower().strip()
        if not email:
            return None
        record = session.execute(
            select(UserModel.user_id).where(
                UserModel.email == email,
                UserModel.client_id == client_id,
            )
        ).scalar_one_or_none()
        resolved = self._clean_uuid(record)
        return resolved or None

    def _clean_uuid(self, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            return str(uuid.UUID(raw))
        except (ValueError, TypeError, AttributeError):
            return ""

    def _ensure_agent_user(self, session: Session, client_id: str) -> AuthenticatedUser:
        email = f"sales-agent+{client_id.split('-')[0]}@easy-ecom.local"
        user = session.execute(
            select(UserModel).where(UserModel.email == email)
        ).scalar_one_or_none()
        if user is None:
            user = UserModel(
                user_id=new_uuid(),
                client_id=client_id,
                user_code=slugify_identifier(f"{client_id}-sales-agent", max_length=160, default="sales-agent"),
                name="Sales Agent",
                email=email,
                password="",
                password_hash="",
                is_active=False,
            )
            session.add(user)
            session.flush()
            session.add(UserRoleModel(user_id=user.user_id, role_code="CLIENT_OWNER"))
        allowed_pages = list(default_page_names_for_roles(["CLIENT_OWNER"]))
        if "Sales Agent" not in allowed_pages:
            allowed_pages.append("Sales Agent")
        return AuthenticatedUser(
            user_id=str(user.user_id),
            client_id=client_id,
            name=user.name,
            email=user.email,
            business_name=None,
            roles=["CLIENT_OWNER"],
            allowed_pages=allowed_pages,
        )

    def _log_audit(
        self,
        session: Session,
        *,
        client_id: str,
        actor_user_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        session.add(
            AuditLogModel(
                audit_log_id=new_uuid(),
                client_id=client_id,
                actor_user_id=actor_user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                metadata_json=metadata_json,
            )
        )

    def _require_sales_agent_access(self, user: AuthenticatedUser) -> None:
        if "SUPER_ADMIN" in user.roles:
            return
        if "Sales Agent" not in user.allowed_pages:
            raise ApiException(status_code=403, code="ACCESS_DENIED", message="Access denied for Sales Agent")

    def _require_owner_or_admin(self, user: AuthenticatedUser) -> None:
        if "SUPER_ADMIN" in user.roles or "CLIENT_OWNER" in user.roles:
            return
        raise ApiException(status_code=403, code="ACCESS_DENIED", message="Client owner or super admin access is required")

    def _require(
        self,
        condition: bool,
        *,
        message: str,
        code: str = "INVALID_REQUEST",
        status_code: int = 400,
    ) -> None:
        if not condition:
            raise ApiException(status_code=status_code, code=code, message=message)
