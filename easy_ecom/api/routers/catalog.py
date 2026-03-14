from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.commerce import (
    CatalogUpsertRequest,
    CatalogUpsertResponse,
    CatalogWorkspaceResponse,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/overview", response_model=ModuleOverviewResponse)
def catalog_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    require_page_access(user, "Catalog")
    return container.overview.catalog(user)


@router.get("/workspace", response_model=CatalogWorkspaceResponse)
def catalog_workspace(
    q: str = Query(default=""),
    location_id: str | None = Query(default=None),
    include_oos: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogWorkspaceResponse:
    return CatalogWorkspaceResponse.model_validate(
        container.catalog.workspace(user, query=q, location_id=location_id, include_oos=include_oos)
    )


@router.post("/products", response_model=CatalogUpsertResponse)
def create_product(
    payload: CatalogUpsertRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogUpsertResponse:
    product = container.catalog.upsert_product(
        user,
        product_id=None,
        identity=payload.identity.model_dump(),
        variants=[item.model_dump() for item in payload.variants],
    )
    return CatalogUpsertResponse(product=product)


@router.put("/products/{product_id}", response_model=CatalogUpsertResponse)
def update_product(
    product_id: str,
    payload: CatalogUpsertRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogUpsertResponse:
    product = container.catalog.upsert_product(
        user,
        product_id=product_id,
        identity=payload.identity.model_dump(),
        variants=[item.model_dump() for item in payload.variants],
    )
    return CatalogUpsertResponse(product=product)
