from __future__ import annotations

from pydantic import BaseModel, Field


class ChannelIntegrationResponse(BaseModel):
    channel_id: str
    provider: str
    display_name: str
    status: str
    external_account_id: str
    verify_token_set: bool
    inbound_secret_set: bool
    config: dict[str, str]
    created_at: str
    updated_at: str
    last_inbound_at: str | None


class ChannelIntegrationListResponse(BaseModel):
    items: list[ChannelIntegrationResponse]


class ChannelIntegrationCreateRequest(BaseModel):
    provider: str = Field(pattern="^(whatsapp|messenger|webhook)$")
    display_name: str = Field(min_length=1, max_length=255)
    external_account_id: str = Field(default="", max_length=255)
    status: str = Field(default="inactive", pattern="^(inactive|active|disabled)$")
    verify_token: str = Field(default="", max_length=255)
    inbound_secret: str = Field(default="", max_length=255)
    config: dict[str, str] = Field(default_factory=dict)


class ChannelIntegrationPatchRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    external_account_id: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(inactive|active|disabled)$")
    verify_token: str | None = Field(default=None, max_length=255)
    inbound_secret: str | None = Field(default=None, max_length=255)
    config: dict[str, str] | None = None


class ChannelMessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    channel_id: str
    direction: str
    external_sender_id: str
    provider_event_id: str
    message_text: str
    content_summary: str
    occurred_at: str
    outbound_status: str


class ChannelMessageListResponse(BaseModel):
    items: list[ChannelMessageResponse]


class InboundEventRequest(BaseModel):
    provider_event_id: str = Field(default="", max_length=255)
    sender_external_id: str = Field(min_length=1, max_length=255)
    sender_name: str | None = Field(default=None, max_length=255)
    message_text: str | None = Field(default=None, max_length=2000)
    occurred_at: str | None = Field(default=None, max_length=64)
    metadata: dict[str, str] = Field(default_factory=dict)


class InboundIngestResponse(BaseModel):
    accepted: bool
    client_id: str
    channel_id: str
    conversation_id: str
    message_id: str


class ConversationResponse(BaseModel):
    conversation_id: str
    channel_id: str
    external_sender_id: str
    status: str
    customer_id: str | None
    linked_sale_id: str | None
    last_message_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]


class ConversationDetailMessage(BaseModel):
    message_id: str
    direction: str
    message_text: str
    content_summary: str
    occurred_at: str
    outbound_status: str


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    channel_id: str
    external_sender_id: str
    status: str
    messages: list[ConversationDetailMessage]


class OutboundPrepareRequest(BaseModel):
    channel_id: str = Field(min_length=1, max_length=64)
    conversation_id: str = Field(min_length=1, max_length=64)
    message_text: str = Field(min_length=1, max_length=2000)
    recipient_external_id: str = Field(min_length=1, max_length=255)
    metadata: dict[str, str] = Field(default_factory=dict)


class OutboundPrepareResponse(BaseModel):
    dispatch_intent_id: str
    status: str
    provider: str
    delivery_deferred: bool
    deferred_reason: str
    ai_context_hint: dict[str, object] | None
