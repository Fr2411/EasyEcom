from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container
from easy_ecom.api.schemas.commerce import SalesOrderActionRequest, SalesOrderActionResponse
from easy_ecom.api.schemas.sales_agent import (
    SalesAgentConversationDetailResponse,
    SalesAgentConversationRowResponse,
    SalesAgentConversationsResponse,
    SalesAgentDraftApproveRequest,
    SalesAgentDraftRejectRequest,
    SalesAgentDraftResponse,
    SalesAgentHandoffRequest,
    SalesAgentOrdersResponse,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


router = APIRouter(prefix="/sales-agent", tags=["sales-agent"])


@router.get("/conversations", response_model=SalesAgentConversationsResponse)
def list_conversations(
    q: str = Query(default=""),
    status: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentConversationsResponse:
    return SalesAgentConversationsResponse(
        items=container.sales_agent.list_conversations(user, query=q, status=status)
    )


@router.get("/conversations/{conversation_id}", response_model=SalesAgentConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentConversationDetailResponse:
    return SalesAgentConversationDetailResponse.model_validate(
        container.sales_agent.get_conversation_detail(user, conversation_id)
    )


@router.post("/conversations/{conversation_id}/handoff", response_model=SalesAgentConversationRowResponse)
def handoff_conversation(
    conversation_id: str,
    payload: SalesAgentHandoffRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentConversationRowResponse:
    return SalesAgentConversationRowResponse.model_validate(
        container.sales_agent.handoff_conversation(user, conversation_id, notes=payload.notes)
    )


@router.post("/drafts/{draft_id}/approve-send", response_model=SalesAgentDraftResponse)
def approve_send_draft(
    draft_id: str,
    payload: SalesAgentDraftApproveRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentDraftResponse:
    return SalesAgentDraftResponse.model_validate(
        container.sales_agent.approve_and_send_draft(user, draft_id, edited_text=payload.edited_text)
    )


@router.post("/drafts/{draft_id}/reject", response_model=SalesAgentDraftResponse)
def reject_draft(
    draft_id: str,
    payload: SalesAgentDraftRejectRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentDraftResponse:
    return SalesAgentDraftResponse.model_validate(
        container.sales_agent.reject_draft(user, draft_id, reason=payload.reason)
    )


@router.get("/orders", response_model=SalesAgentOrdersResponse)
def list_orders(
    status: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentOrdersResponse:
    return SalesAgentOrdersResponse(items=container.sales_agent.list_agent_orders(user, status=status))


@router.post("/orders/{sales_order_id}/confirm", response_model=SalesOrderActionResponse)
def confirm_order(
    sales_order_id: str,
    _payload: SalesOrderActionRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesOrderActionResponse:
    return SalesOrderActionResponse(order=container.sales_agent.confirm_agent_order(user, sales_order_id))
