from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.sales_agent import (
    AiReviewDetailResponse,
    AiReviewQueueResponse,
    SalesAgentDraftApproveRequest,
    SalesAgentDraftRejectRequest,
    SalesAgentDraftResponse,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


router = APIRouter(
    prefix="/ai-review",
    tags=["ai-review"],
    dependencies=[Depends(require_module_access("AI Review"))],
)


@router.get("/drafts", response_model=AiReviewQueueResponse)
def list_ai_review_drafts(
    q: str = Query(default=""),
    status: str | None = Query(default="needs_review"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AiReviewQueueResponse:
    return AiReviewQueueResponse(items=container.sales_agent.list_ai_review_drafts(user, query=q, status=status))


@router.get("/drafts/{draft_id}", response_model=AiReviewDetailResponse)
def get_ai_review_draft(
    draft_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AiReviewDetailResponse:
    return AiReviewDetailResponse.model_validate(container.sales_agent.get_ai_review_draft_detail(user, draft_id))


@router.post("/drafts/{draft_id}/approve-send", response_model=SalesAgentDraftResponse)
def approve_ai_review_draft(
    draft_id: str,
    payload: SalesAgentDraftApproveRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentDraftResponse:
    return SalesAgentDraftResponse.model_validate(
        container.sales_agent.approve_and_send_draft(user, draft_id, edited_text=payload.edited_text)
    )


@router.post("/drafts/{draft_id}/reject", response_model=SalesAgentDraftResponse)
def reject_ai_review_draft(
    draft_id: str,
    payload: SalesAgentDraftRejectRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SalesAgentDraftResponse:
    return SalesAgentDraftResponse.model_validate(
        container.sales_agent.reject_draft(user, draft_id, reason=payload.reason)
    )
