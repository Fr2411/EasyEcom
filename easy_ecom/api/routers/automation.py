from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from easy_ecom.api.dependencies import get_authenticated_user, require_page_access
from easy_ecom.api.schemas.automation import (
    AutomationRuleResponse,
    AutomationRunsResponse,
    AutomationRulesResponse,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.automation_service import AutomationService

router = APIRouter(prefix="/automation", tags=["automation"])


def _service() -> AutomationService:
    return AutomationService()


@router.get("/overview", response_model=ModuleOverviewResponse)
def automation_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> ModuleOverviewResponse:
    require_page_access(user, "Automation")
    return _service().overview(user)


@router.get("/rules", response_model=AutomationRulesResponse)
def list_rules(
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AutomationRulesResponse:
    require_page_access(user, "Automation")
    return _service().list_rules(user)


@router.get("/rules/{rule_id}", response_model=AutomationRuleResponse)
def get_rule(
    rule_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AutomationRuleResponse:
    require_page_access(user, "Automation")
    try:
        return _service().get_rule(user, rule_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/rules/{rule_id}/runs", response_model=AutomationRunsResponse)
def list_rule_runs(
    rule_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AutomationRunsResponse:
    require_page_access(user, "Automation")
    return _service().list_rule_runs(user, rule_id)


@router.get("/runs", response_model=AutomationRunsResponse)
def list_runs(
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AutomationRunsResponse:
    require_page_access(user, "Automation")
    return _service().list_runs(user)
