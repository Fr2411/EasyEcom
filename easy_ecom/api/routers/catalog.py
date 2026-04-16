from fastapi import APIRouter, Depends, File, Query, UploadFile

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.commerce import (
    AttachProductMediaRequest,
    CatalogUpsertRequest,
    CatalogUpsertResponse,
    CatalogWorkspaceResponse,
    StagedProductMediaUploadResponse,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
    dependencies=[Depends(require_module_access("Catalog"))],
)


@router.get("/overview", response_model=ModuleOverviewResponse)
def catalog_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
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


@router.post("/media/staged", response_model=StagedProductMediaUploadResponse)
def create_staged_product_media(
    image: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> StagedProductMediaUploadResponse:
    payload = container.catalog.create_staged_media(user, image)
    return StagedProductMediaUploadResponse.model_validate(payload)


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


@router.post("/products/{product_id}/media", response_model=CatalogUpsertResponse)
def attach_product_media(
    product_id: str,
    payload: AttachProductMediaRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CatalogUpsertResponse:
    product = container.catalog.attach_product_media(
        user,
        product_id=product_id,
        staged_upload_id=payload.upload_id,
    )
    return CatalogUpsertResponse(product=product)
