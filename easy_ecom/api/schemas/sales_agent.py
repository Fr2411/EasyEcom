from __future__ import annotations

from typing import Any
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from easy_ecom.api.schemas.commerce import LocationSummaryResponse, SalesOrderResponse


class ChannelIntegrationResponse(BaseModel):
    channel_id: str
    provider: str
    display_name: str
    status: str
    config_saved: bool
    webhook_key: str
    external_account_id: str
    phone_number_id: str
    phone_number: str
    verify_token_set: bool
    inbound_secret_set: bool
    access_token_set: bool
    webhook_verified_at: str | None
    last_webhook_post_at: str | None
    signature_validation_ok: bool | None
    graph_auth_ok: bool | None
    outbound_send_ok: bool | None
    openai_ready: bool
    openai_probe_ok: bool | None
    last_error_code: str | None
    last_error_message: str | None
    last_provider_status_code: int | None
    last_provider_response_excerpt: str | None
    last_diagnostic_at: str | None
    next_action: str
    default_location_id: str | None
    auto_send_enabled: bool
    agent_enabled: bool
    model_name: str
    persona_prompt: str
    config: dict[str, str]
    created_at: str
    updated_at: str
    last_inbound_at: str | None
    last_outbound_at: str | None


class ChannelIntegrationsResponse(BaseModel):
    items: list[ChannelIntegrationResponse]


class ChannelLocationsResponse(BaseModel):
    items: list[LocationSummaryResponse]


class WhatsAppMetaIntegrationRequest(BaseModel):
    display_name: str = "WhatsApp Sales Agent"
    external_account_id: str = ""
    phone_number_id: str = Field(min_length=1, max_length=128)
    phone_number: str = ""
    verify_token: str = ""
    access_token: str = ""
    app_secret: str = ""
    default_location_id: str | None = None
    auto_send_enabled: bool = False
    agent_enabled: bool = True
    model_name: str = "gpt-4o-mini"
    persona_prompt: str = ""


class WhatsAppMetaIntegrationResponse(BaseModel):
    channel: ChannelIntegrationResponse
    setup_verify_token: str | None = None


class ChannelDiagnosticsResponse(BaseModel):
    config_saved: bool
    verify_token_set: bool
    webhook_verified_at: str | None
    last_webhook_post_at: str | None
    signature_validation_ok: bool | None
    graph_auth_ok: bool | None
    outbound_send_ok: bool | None
    openai_ready: bool
    openai_probe_ok: bool | None
    last_error_code: str | None
    last_error_message: str | None
    last_provider_status_code: int | None
    last_provider_response_excerpt: str | None
    last_diagnostic_at: str | None
    next_action: str


class ChannelDiagnosticsEnvelopeResponse(BaseModel):
    diagnostics: ChannelDiagnosticsResponse
    provider_details: dict[str, Any]


class ChannelRunDiagnosticsResponse(BaseModel):
    channel: ChannelIntegrationResponse
    diagnostics: ChannelDiagnosticsResponse
    provider_details: dict[str, Any]


class ChannelSmokeRequest(BaseModel):
    recipient: str = Field(min_length=5, max_length=64)
    text: str = Field(default="EasyEcom smoke test. Reply path is working.", max_length=1000)


class ChannelSmokeResponse(BaseModel):
    ok: bool
    provider_event_id: str | None
    message: str
    diagnostics: ChannelDiagnosticsResponse
    provider_details: dict[str, Any]


class SalesAgentMentionResponse(BaseModel):
    mention_id: str
    product_id: str | None
    variant_id: str | None
    mention_role: str
    quantity: Decimal | None
    unit_price: Decimal | None
    min_price: Decimal | None
    available_to_sell: Decimal | None


class SalesAgentMessageResponse(BaseModel):
    message_id: str
    direction: str
    message_text: str
    content_summary: str
    occurred_at: str
    outbound_status: str
    provider_status: str
    mentions: list[SalesAgentMentionResponse]


class SalesAgentDraftResponse(BaseModel):
    draft_id: str
    conversation_id: str
    linked_sales_order_id: str | None
    status: str
    ai_draft_text: str
    edited_text: str
    final_text: str
    intent: str
    confidence: Decimal | None
    grounding: dict[str, object]
    reason_codes: list[str]
    approved_at: str | None
    sent_at: str | None
    failed_reason: str | None
    human_modified: bool


class SalesAgentConversationRowResponse(BaseModel):
    conversation_id: str
    channel_id: str
    customer_id: str | None
    customer_name: str
    customer_phone: str
    customer_email: str
    external_sender_id: str
    status: str
    customer_type: str
    behavior_tags: list[str]
    lifetime_spend: Decimal
    lifetime_order_count: int
    latest_intent: str
    latest_summary: str
    last_message_preview: str
    last_message_at: str | None
    latest_recommended_products_summary: str
    linked_draft_order_id: str | None
    linked_draft_order_status: str
    latest_draft_id: str | None
    latest_draft_status: str | None
    latest_trace: dict[str, object] = Field(default_factory=dict)
    linked_order: SalesOrderResponse | None


class SalesAgentConversationsResponse(BaseModel):
    items: list[SalesAgentConversationRowResponse]


class SalesAgentConversationDetailResponse(SalesAgentConversationRowResponse):
    messages: list[SalesAgentMessageResponse]
    latest_draft: SalesAgentDraftResponse | None


class SalesAgentHandoffRequest(BaseModel):
    notes: str = ""


class SalesAgentDraftApproveRequest(BaseModel):
    edited_text: str = ""


class SalesAgentDraftRejectRequest(BaseModel):
    reason: str = ""


class SalesAgentOrdersResponse(BaseModel):
    items: list[SalesOrderResponse]
