from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


BusinessType = Literal["general_retail", "pet_food", "fashion", "shoe_store", "electronics", "cosmetics", "grocery"]
BrandPersonality = Literal["friendly", "expert", "premium", "casual", "concise"]
ChannelProvider = Literal["website", "whatsapp", "instagram", "facebook", "messenger", "other"]


class AssistantPlaybookResponse(BaseModel):
    playbook_id: str
    status: str
    business_type: str
    brand_personality: str
    custom_instructions: str
    forbidden_claims: str
    sales_goals: dict[str, Any]
    policies: dict[str, Any]
    escalation_rules: dict[str, Any]
    industry_template: dict[str, Any]


class AssistantPlaybookUpdateRequest(BaseModel):
    business_type: BusinessType = "general_retail"
    brand_personality: BrandPersonality = "friendly"
    custom_instructions: str = Field(default="", max_length=6000)
    forbidden_claims: str = Field(default="", max_length=4000)
    sales_goals: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(default_factory=dict)
    escalation_rules: dict[str, Any] = Field(default_factory=dict)


class CustomerChannelResponse(BaseModel):
    channel_id: str
    provider: str
    display_name: str
    status: str
    external_account_id: str
    webhook_key: str
    default_location_id: str | None
    auto_send_enabled: bool
    config: dict[str, Any]
    last_inbound_at: str | None
    last_outbound_at: str | None


class CustomerChannelUpsertRequest(BaseModel):
    provider: ChannelProvider = "website"
    display_name: str = Field(min_length=2, max_length=255)
    status: Literal["active", "inactive"] = "active"
    external_account_id: str = Field(default="", max_length=128)
    default_location_id: str | None = None
    auto_send_enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class CustomerMessageResponse(BaseModel):
    message_id: str
    conversation_id: str
    channel_id: str
    direction: str
    sender_role: str
    provider_event_id: str
    message_text: str
    outbound_status: str
    metadata: dict[str, Any]
    occurred_at: str | None


class AssistantToolCallResponse(BaseModel):
    tool_call_id: str
    run_id: str
    tool_name: str
    tool_arguments: dict[str, Any]
    tool_result: dict[str, Any]
    validation_status: str
    created_at: str | None


class AssistantRunResponse(BaseModel):
    run_id: str
    conversation_id: str
    inbound_message_id: str
    status: str
    model_provider: str
    model_name: str
    response_text: str
    validation_status: str
    escalation_required: bool
    escalation_reason: str
    total_tokens: int | None
    created_at: str | None
    tool_calls: list[AssistantToolCallResponse] = Field(default_factory=list)


class CustomerConversationSummaryResponse(BaseModel):
    conversation_id: str
    channel_id: str
    channel_provider: str
    channel_display_name: str
    customer_id: str | None
    draft_order_id: str | None
    external_sender_id: str
    external_sender_name: str
    external_sender_phone: str
    external_sender_email: str
    status: str
    latest_intent: str
    latest_summary: str
    escalation_reason: str
    last_message_preview: str
    last_message_at: str | None


class CustomerConversationDetailResponse(CustomerConversationSummaryResponse):
    memory: dict[str, Any]
    messages: list[CustomerMessageResponse]
    runs: list[AssistantRunResponse]


class CustomerCommunicationWorkspaceResponse(BaseModel):
    playbook: AssistantPlaybookResponse
    channels: list[CustomerChannelResponse]
    conversations: list[CustomerConversationSummaryResponse]
    active_conversation: CustomerConversationDetailResponse | None = None


class PublicCustomerChatRequest(BaseModel):
    external_sender_id: str = Field(min_length=1, max_length=160)
    message_text: str = Field(min_length=1, max_length=4000)
    sender_name: str = Field(default="", max_length=255)
    sender_phone: str = Field(default="", max_length=64)
    sender_email: str = Field(default="", max_length=255)
    provider_event_id: str = Field(default="", max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message_text")
    @classmethod
    def clean_message(cls, value: str) -> str:
        return " ".join(value.strip().split())


class PublicCustomerChatResponse(BaseModel):
    conversation: CustomerConversationSummaryResponse
    inbound_message: CustomerMessageResponse
    outbound_message: CustomerMessageResponse | None
    assistant_run: AssistantRunResponse | None


class ProviderWebhookMessage(BaseModel):
    external_sender_id: str = Field(min_length=1, max_length=160)
    message_text: str = Field(min_length=1, max_length=4000)
    sender_name: str = ""
    sender_phone: str = ""
    sender_email: str = ""
    provider_event_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DraftOrderLineInput(BaseModel):
    variant_id: str
    quantity: Decimal = Field(gt=Decimal("0"))


class AssistantDraftOrderRequest(BaseModel):
    conversation_id: str
    customer_name: str = ""
    customer_phone: str = ""
    customer_email: str = ""
    location_id: str | None = None
    lines: list[DraftOrderLineInput] = Field(default_factory=list)
