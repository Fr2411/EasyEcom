from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewConversationRow(BaseModel):
    conversation_id: str
    channel_id: str
    external_sender_id: str
    customer_id: str | None
    status: str
    last_message_at: str
    preview_message_id: str
    preview_text: str


class ReviewConversationListResponse(BaseModel):
    items: list[ReviewConversationRow]


class AiReviewDraftResponse(BaseModel):
    draft_id: str
    conversation_id: str
    inbound_message_id: str
    status: str
    ai_draft_text: str
    edited_text: str
    final_text: str
    intent: str
    confidence: str
    grounding: dict[str, object]
    requested_by_user_id: str
    approved_by_user_id: str | None
    sent_by_user_id: str | None
    created_at: str
    updated_at: str
    approved_at: str | None
    sent_at: str | None
    failed_reason: str | None
    send_result: dict[str, object]
    human_modified: bool


class ReviewConversationDetailMessage(BaseModel):
    message_id: str
    direction: str
    message_text: str
    content_summary: str
    occurred_at: str
    outbound_status: str


class ReviewConversationDetailResponse(BaseModel):
    conversation_id: str
    channel_id: str
    external_sender_id: str
    status: str
    messages: list[ReviewConversationDetailMessage]
    latest_draft: AiReviewDraftResponse | None


class CreateDraftRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=64)
    inbound_message_id: str = Field(min_length=1, max_length=64)


class EditDraftRequest(BaseModel):
    edited_text: str = Field(min_length=1, max_length=2000)


class ReviewHistoryResponse(BaseModel):
    items: list[AiReviewDraftResponse]
