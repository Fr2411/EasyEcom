from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from easy_ecom.api.dependencies import RequestUser, ServiceContainer, get_container, get_current_user, require_page_access
from easy_ecom.api.schemas.automation import (
    AutomationDecisionListResponse,
    AutomationDecisionResponse,
    AutomationEnableDisableRequest,
    AutomationEvaluationResponse,
    AutomationPolicyPatchRequest,
    AutomationPolicyResponse,
)
from easy_ecom.core.rbac import ADMIN_MANAGE_USERS_ROLES, has_any_role
from easy_ecom.domain.services.automation_service import AutomationPolicyPatch

router = APIRouter(prefix="/automation", tags=["automation"])


def _require_admin_role(user: RequestUser) -> None:
    if not has_any_role(user.roles, ADMIN_MANAGE_USERS_ROLES):
        raise HTTPException(status_code=403, detail="Admin or manager role required")


def _require_service(container: ServiceContainer):
    service = getattr(container, "automation", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Automation API requires postgres backend")
    return service


@router.get("/policies", response_model=AutomationPolicyResponse)
def get_policy(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationPolicyResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    return AutomationPolicyResponse(**service.get_policy(client_id=user.client_id))


@router.patch("/policies", response_model=AutomationPolicyResponse)
def patch_policy(
    payload: AutomationPolicyPatchRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationPolicyResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.patch_policy(
            client_id=user.client_id,
            updated_by_user_id=user.user_id,
            payload=AutomationPolicyPatch(**payload.model_dump(exclude_none=True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AutomationPolicyResponse(**row)


@router.post("/enable", response_model=AutomationPolicyResponse)
def enable_automation(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationPolicyResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    return AutomationPolicyResponse(**service.enable(client_id=user.client_id, updated_by_user_id=user.user_id))


@router.post("/disable", response_model=AutomationPolicyResponse)
def disable_automation(
    payload: AutomationEnableDisableRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationPolicyResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    return AutomationPolicyResponse(**service.disable(client_id=user.client_id, updated_by_user_id=user.user_id, emergency=payload.emergency))


@router.post("/evaluate/{conversation_id}", response_model=AutomationEvaluationResponse)
def evaluate_automation(
    conversation_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationEvaluationResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.evaluate(client_id=user.client_id, conversation_id=conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AutomationEvaluationResponse(**row)


@router.post("/run/{conversation_id}", response_model=AutomationDecisionResponse)
def run_automation(
    conversation_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationDecisionResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.run(client_id=user.client_id, conversation_id=conversation_id, run_by_user_id=user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AutomationDecisionResponse(**row)


@router.get("/history", response_model=AutomationDecisionListResponse)
def get_history(
    limit: int = Query(default=100, ge=1, le=200),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationDecisionListResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    return AutomationDecisionListResponse(items=service.list_history(client_id=user.client_id, limit=limit))


@router.get("/queue", response_model=AutomationDecisionListResponse)
def get_queue(
    limit: int = Query(default=100, ge=1, le=200),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AutomationDecisionListResponse:
    require_page_access(user, "Automation")
    _require_admin_role(user)
    service = _require_service(container)
    return AutomationDecisionListResponse(items=service.list_queue(client_id=user.client_id, limit=limit))
