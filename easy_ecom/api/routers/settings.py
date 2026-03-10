from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
    require_page_access,
)
from easy_ecom.api.schemas.settings import (
    BusinessProfilePatchRequest,
    BusinessProfileResponse,
    PreferencesPatchRequest,
    PreferencesResponse,
    SequencePatchRequest,
    SequenceResponse,
    TenantContextResponse,
)
from easy_ecom.core.rbac import ADMIN_MANAGE_USERS_ROLES, has_any_role
from easy_ecom.domain.services.settings_api_service import (
    BusinessProfilePatch,
    OperationalPreferencesPatch,
    SequencePreferencesPatch,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _require_service(container: ServiceContainer):
    service = getattr(container, "settings_mvp", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Settings API requires postgres backend")
    return service


def _require_settings_write_role(user: RequestUser) -> None:
    if not has_any_role(user.roles, ADMIN_MANAGE_USERS_ROLES):
        raise HTTPException(status_code=403, detail="Admin or manager role required for settings updates")


@router.get("/business-profile", response_model=BusinessProfileResponse)
def get_business_profile(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> BusinessProfileResponse:
    require_page_access(user, "Settings")
    service = _require_service(container)
    profile = service.get_business_profile(client_id=user.client_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return BusinessProfileResponse(**profile)


@router.patch("/business-profile", response_model=BusinessProfileResponse)
def patch_business_profile(
    payload: BusinessProfilePatchRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> BusinessProfileResponse:
    require_page_access(user, "Settings")
    _require_settings_write_role(user)
    if not payload.model_dump(exclude_none=True):
        raise HTTPException(status_code=400, detail="No fields provided")
    service = _require_service(container)
    updated = service.patch_business_profile(
        client_id=user.client_id,
        payload=BusinessProfilePatch(**payload.model_dump(exclude_none=True)),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return BusinessProfileResponse(**updated)


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PreferencesResponse:
    require_page_access(user, "Settings")
    service = _require_service(container)
    preferences = service.get_preferences(client_id=user.client_id)
    if preferences is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return PreferencesResponse(**preferences)


@router.patch("/preferences", response_model=PreferencesResponse)
def patch_preferences(
    payload: PreferencesPatchRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> PreferencesResponse:
    require_page_access(user, "Settings")
    _require_settings_write_role(user)
    if not payload.model_dump(exclude_none=True):
        raise HTTPException(status_code=400, detail="No fields provided")
    service = _require_service(container)
    try:
        updated = service.patch_preferences(
            client_id=user.client_id,
            payload=OperationalPreferencesPatch(**payload.model_dump(exclude_none=True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return PreferencesResponse(**updated)


@router.get("/sequences", response_model=SequenceResponse)
def get_sequences(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SequenceResponse:
    require_page_access(user, "Settings")
    service = _require_service(container)
    data = service.get_sequences(client_id=user.client_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return SequenceResponse(**data)


@router.patch("/sequences", response_model=SequenceResponse)
def patch_sequences(
    payload: SequencePatchRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> SequenceResponse:
    require_page_access(user, "Settings")
    _require_settings_write_role(user)
    if not payload.model_dump(exclude_none=True):
        raise HTTPException(status_code=400, detail="No fields provided")
    service = _require_service(container)
    try:
        updated = service.patch_sequences(
            client_id=user.client_id,
            payload=SequencePreferencesPatch(**payload.model_dump(exclude_none=True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return SequenceResponse(**updated)


@router.get("/tenant-context", response_model=TenantContextResponse)
def tenant_context(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> TenantContextResponse:
    require_page_access(user, "Settings")
    service = _require_service(container)
    data = service.get_tenant_context(client_id=user.client_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return TenantContextResponse(**data)
