from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(require_module_access("Customers"))],
)


@router.get("/overview", response_model=ModuleOverviewResponse)
def customers_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    return container.overview.customers(user)
