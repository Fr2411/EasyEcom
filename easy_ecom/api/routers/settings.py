from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/overview", response_model=ModuleOverviewResponse)
def settings_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    require_page_access(user, "Settings")
    return container.overview.settings(user)
