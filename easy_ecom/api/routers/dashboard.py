from datetime import date

from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.dashboard import DashboardAnalyticsResponse
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_module_access("Dashboard"))],
)


@router.get("/overview", response_model=ModuleOverviewResponse)
def dashboard_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    return container.overview.dashboard(user)


@router.get("/analytics", response_model=DashboardAnalyticsResponse)
def dashboard_analytics(
    range_key: str = Query(default="mtd"),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    location_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> DashboardAnalyticsResponse:
    return DashboardAnalyticsResponse.model_validate(
        container.dashboard.analytics(
            user,
            range_key=range_key,
            from_date=from_date,
            to_date=to_date,
            location_id=location_id,
        )
    )
