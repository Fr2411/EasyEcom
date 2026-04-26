from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from easy_ecom.api.schemas.commerce import SalesOrderResponse


class AIAgentFAQEntry(BaseModel):
    question: str = Field(default="", max_length=500)
    answer: str = Field(default="", max_length=2000)


class AIAgentAllowedActions(BaseModel):
    product_qa: bool = True
    recommendations: bool = True
    cart_building: bool = True
    order_confirmation: bool = True


class AIAgentSettingsResponse(BaseModel):
    profile_id: str
    channel_id: str
    widget_key: str
    ai_runtime: str
    model_name: str
    model_configured: bool
    channel_status: str
    is_enabled: bool
    display_name: str
    persona_prompt: str
    store_policy: str
    faq_entries: list[AIAgentFAQEntry]
    escalation_rules: list[str]
    allowed_origins: list[str]
    allowed_actions: AIAgentAllowedActions
    default_location_id: str | None
    opening_message: str
    handoff_message: str
    chat_link: str
    widget_script: str


class AIAgentSettingsUpdateRequest(BaseModel):
    channel_status: Literal["active", "inactive"] = "active"
    is_enabled: bool = False
    display_name: str = Field(default="Website sales assistant", min_length=2, max_length=255)
    persona_prompt: str = ""
    store_policy: str = ""
    faq_entries: list[AIAgentFAQEntry] = Field(default_factory=list)
    escalation_rules: list[str] = Field(default_factory=list)
    allowed_origins: list[str] = Field(default_factory=list)
    allowed_actions: AIAgentAllowedActions = Field(default_factory=AIAgentAllowedActions)
    default_location_id: str | None = None
    opening_message: str = ""
    handoff_message: str = ""

    @field_validator("persona_prompt", "store_policy", "opening_message", "handoff_message", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("allowed_origins", "escalation_rules", mode="before")
    @classmethod
    def normalize_string_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("default_location_id", mode="before")
    @classmethod
    def blank_location_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AIConversationSummaryResponse(BaseModel):
    conversation_id: str
    channel_id: str
    channel_type: str
    channel_display_name: str
    status: str
    customer_name: str
    customer_phone: str
    customer_email: str
    latest_intent: str
    latest_summary: str
    handoff_reason: str
    last_message_preview: str
    last_message_at: str | None
    message_count: int


class AIConversationListResponse(BaseModel):
    items: list[AIConversationSummaryResponse]


class AIChatCustomerInput(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""


class PublicChatMessageRequest(BaseModel):
    browser_session_id: str = Field(min_length=8, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    customer: AIChatCustomerInput | None = None
    metadata: dict[str, Any] | None = None


class PublicChatMessageResponse(BaseModel):
    conversation_id: str
    inbound_message_id: str
    outbound_message_id: str | None = None
    reply_text: str
    status: str
    handoff_required: bool = False
    handoff_reason: str = ""
    order_status: str | None = None


class AIToolContextResponse(BaseModel):
    client_id: str
    channel_id: str
    conversation_id: str
    business: dict[str, Any]
    agent: dict[str, Any]
    customer: dict[str, Any]
    recent_messages: list[dict[str, Any]]
    tool_rules: list[str]


class AIToolBaseRequest(BaseModel):
    client_id: str
    conversation_id: str


class AICatalogSearchRequest(AIToolBaseRequest):
    query: str = Field(min_length=1, max_length=255)
    location_id: str | None = None
    include_out_of_stock: bool = False
    limit: int = Field(default=8, ge=1, le=20)


class AICatalogSearchResponse(BaseModel):
    items: list[dict[str, Any]]


class AIVariantAvailabilityRequest(AIToolBaseRequest):
    variant_id: str
    quantity: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))
    location_id: str | None = None


class AIVariantAvailabilityResponse(BaseModel):
    variant: dict[str, Any]
    requested_quantity: Decimal
    can_fulfill: bool


class AIConversationStateRequest(AIToolBaseRequest):
    status: Literal["open", "handoff", "closed"] | None = None
    latest_intent: str = ""
    latest_summary: str = ""
    customer: AIChatCustomerInput | None = None
    metadata: dict[str, Any] | None = None


class AIConversationStateResponse(BaseModel):
    conversation_id: str
    status: str
    latest_intent: str
    latest_summary: str


class AIOrderLineInput(BaseModel):
    variant_id: str
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_price: Decimal | None = None
    discount_amount: Decimal = Decimal("0")


class AIConfirmOrderRequest(AIToolBaseRequest):
    customer: AIChatCustomerInput
    lines: list[AIOrderLineInput] = Field(min_length=1)
    customer_confirmed: bool = False
    confirmation_text: str = ""
    location_id: str | None = None
    notes: str = ""


class AIConfirmOrderResponse(BaseModel):
    order: SalesOrderResponse


class AIHandoffRequest(AIToolBaseRequest):
    reason: str = Field(min_length=2, max_length=1000)
    summary: str = ""


class AIHandoffResponse(BaseModel):
    conversation_id: str
    status: Literal["handoff"]
    handoff_reason: str
