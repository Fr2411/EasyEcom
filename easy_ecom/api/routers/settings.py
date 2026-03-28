from fastapi import APIRouter, Depends, Request
from dataclasses import asdict

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_page_access
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.api.schemas.settings import SettingsWorkspaceResponse, SettingsWorkspaceUpdateRequest
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.settings_service import SettingsWorkspaceRecord

router = APIRouter(prefix="/settings", tags=["settings"])


def _serialize_workspace(record: SettingsWorkspaceRecord) -> SettingsWorkspaceResponse:
    return SettingsWorkspaceResponse.model_validate(asdict(record))


@router.get("/overview", response_model=ModuleOverviewResponse)
def settings_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    require_page_access(user, "Settings")
    return container.overview.settings(user)


@router.get("/workspace", response_model=SettingsWorkspaceResponse)
def get_settings_workspace(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SettingsWorkspaceResponse:
    require_page_access(user, "Settings")
    return _serialize_workspace(container.settings.get_workspace(user))


@router.put("/workspace", response_model=SettingsWorkspaceResponse)
def update_settings_workspace(
    payload: SettingsWorkspaceUpdateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> SettingsWorkspaceResponse:
    require_page_access(user, "Settings")
    return _serialize_workspace(
        container.settings.update_workspace(
            user,
            request_id=getattr(request.state, "request_id", None),
            profile=payload.profile.model_dump(),
            defaults=payload.defaults.model_dump(),
            prefixes=payload.prefixes.model_dump(),
        )
    )
