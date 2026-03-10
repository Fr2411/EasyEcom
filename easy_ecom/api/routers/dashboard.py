from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.dashboard import DashboardOverviewResponse, DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def summary(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> DashboardSummaryResponse:
    require_page_access(user, "Dashboard")
    snapshot = container.dashboard.business_health_snapshot(user.client_id)
    return DashboardSummaryResponse(
        Revenue=snapshot["Revenue"],
        Gross_Profit=snapshot["Gross Profit"],
        Net_Operating_Profit=snapshot["Net Operating Profit"],
        Gross_Margin_Pct=snapshot["Gross Margin %"],
        Inventory_Value=snapshot["Inventory Value"],
        Outstanding_Receivables=snapshot["Outstanding Receivables"],
        Data_Health_Score=snapshot["Data Health Score"],
    )


@router.get("/overview", response_model=DashboardOverviewResponse)
def overview(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> DashboardOverviewResponse:
    require_page_access(user, "Dashboard")
    snapshot = container.dashboard.overview_snapshot(user.client_id)
    return DashboardOverviewResponse(**snapshot)
