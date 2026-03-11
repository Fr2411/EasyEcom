from __future__ import annotations

from pydantic import BaseModel, Field


class AutomationPolicyResponse(BaseModel):
    policy_id: str
    client_id: str
    automation_enabled: bool
    auto_send_enabled: bool
    emergency_disabled: bool
    categories: dict[str, bool]
    updated_by_user_id: str
    created_at: str
    updated_at: str


class AutomationPolicyPatchRequest(BaseModel):
    automation_enabled: bool | None = None
    auto_send_enabled: bool | None = None
    emergency_disabled: bool | None = None
    categories: dict[str, bool] | None = None


class AutomationEvaluationResponse(BaseModel):
    conversation_id: str
    inbound_message_id: str
    category: str
    classification_rule: str
    automation_eligible: bool
    recommended_action: str
    reason: str
    candidate_reply: str | None = None
    intent: str | None = None
    confidence: str | None = None
    grounding: dict[str, object] | None = None


class AutomationDecisionResponse(BaseModel):
    decision_id: str
    conversation_id: str
    inbound_message_id: str
    policy_id: str
    category: str
    classification_rule: str
    recommended_action: str
    outcome: str
    reason: str
    confidence: str
    candidate_reply: str
    audit_context: dict[str, object]
    run_by_user_id: str
    created_at: str
    updated_at: str


class AutomationDecisionListResponse(BaseModel):
    items: list[AutomationDecisionResponse]


class AutomationEnableDisableRequest(BaseModel):
    emergency: bool = Field(default=False)
