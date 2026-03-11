from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import RequestUser, ServiceContainer, get_container, get_current_user, require_page_access
from easy_ecom.api.schemas.ai_review import (
    AiReviewDraftResponse,
    CreateDraftRequest,
    EditDraftRequest,
    ReviewConversationDetailResponse,
    ReviewConversationListResponse,
    ReviewHistoryResponse,
)
from easy_ecom.core.rbac import ADMIN_MANAGE_USERS_ROLES, has_any_role
from easy_ecom.domain.services.ai_review_service import DraftCreatePayload, DraftEditPayload

router = APIRouter(prefix="/ai/review", tags=["ai-review"])


def _require_admin_role(user: RequestUser) -> None:
    if not has_any_role(user.roles, ADMIN_MANAGE_USERS_ROLES):
        raise HTTPException(status_code=403, detail="Admin or manager role required")


def _require_service(container: ServiceContainer):
    service = getattr(container, "ai_review", None)
    if service is None:
        raise HTTPException(status_code=501, detail="AI review API requires postgres backend")
    return service


@router.get("/conversations", response_model=ReviewConversationListResponse)
def list_review_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReviewConversationListResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    return ReviewConversationListResponse(items=service.list_review_conversations(client_id=user.client_id, limit=limit))


@router.get("/conversations/{conversation_id}", response_model=ReviewConversationDetailResponse)
def get_review_conversation(
    conversation_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReviewConversationDetailResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    row = service.get_review_conversation(client_id=user.client_id, conversation_id=conversation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ReviewConversationDetailResponse(**row)


@router.post("/draft", response_model=AiReviewDraftResponse)
def create_draft(
    payload: CreateDraftRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiReviewDraftResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.create_draft(
            client_id=user.client_id,
            requested_by_user_id=user.user_id,
            payload=DraftCreatePayload(**payload.model_dump()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AiReviewDraftResponse(**row)


@router.post("/{draft_id}/edit", response_model=AiReviewDraftResponse)
def edit_draft(
    draft_id: str,
    payload: EditDraftRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiReviewDraftResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.edit_draft(client_id=user.client_id, draft_id=draft_id, payload=DraftEditPayload(**payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AiReviewDraftResponse(**row)


@router.post("/{draft_id}/approve", response_model=AiReviewDraftResponse)
def approve_draft(
    draft_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiReviewDraftResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.approve_draft(client_id=user.client_id, draft_id=draft_id, approved_by_user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AiReviewDraftResponse(**row)


@router.post("/{draft_id}/reject", response_model=AiReviewDraftResponse)
def reject_draft(
    draft_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiReviewDraftResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.reject_draft(client_id=user.client_id, draft_id=draft_id, rejected_by_user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AiReviewDraftResponse(**row)


@router.post("/{draft_id}/send", response_model=AiReviewDraftResponse)
def send_draft(
    draft_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AiReviewDraftResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.send_draft(client_id=user.client_id, draft_id=draft_id, sent_by_user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AiReviewDraftResponse(**row)


@router.get("/history", response_model=ReviewHistoryResponse)
def get_history(
    limit: int = Query(default=100, ge=1, le=200),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ReviewHistoryResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    return ReviewHistoryResponse(items=service.list_history(client_id=user.client_id, limit=limit))
