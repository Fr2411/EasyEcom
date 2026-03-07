from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.dashboard import DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def summary(
    client_id: str = "",
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> DashboardSummaryResponse:
    require_page_access(user, "Dashboard")
    scoped_client = client_id or user.client_id
    snapshot = container.dashboard.business_health_snapshot(scoped_client)
    return DashboardSummaryResponse(
        Revenue=snapshot["Revenue"],
        Gross_Profit=snapshot["Gross Profit"],
        Net_Operating_Profit=snapshot["Net Operating Profit"],
        Gross_Margin_Pct=snapshot["Gross Margin %"],
        Inventory_Value=snapshot["Inventory Value"],
        Outstanding_Receivables=snapshot["Outstanding Receivables"],
        Data_Health_Score=snapshot["Data Health Score"],
    )
