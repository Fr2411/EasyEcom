from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container
from easy_ecom.api.schemas.admin import (
    AdminAuditItemResponse,
    AdminAuditResponse,
    AdminClientResponse,
    AdminClientsResponse,
    AdminClientUpdateRequest,
    AdminOnboardClientRequest,
    AdminOnboardResponse,
    AdminRolesResponse,
    AdminRoleAccessResponse,
    AdminUserCreateRequest,
    AdminUserResponse,
    AdminUsersResponse,
    AdminUserUpdateRequest,
)
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.core.errors import ApiException
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.admin_service import (
    AdminAuditEntry,
    AdminClientRecord,
    AdminOnboardResult,
    AdminRoleAccess,
    AdminUserRecord,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_super_admin(user: AuthenticatedUser) -> None:
    if "SUPER_ADMIN" not in user.roles:
        raise ApiException(
            status_code=403,
            code="ACCESS_DENIED",
            message="Super admin access is required",
        )


def _serialize_client(record: AdminClientRecord) -> AdminClientResponse:
    return AdminClientResponse(
        client_id=record.client_id,
        client_code=record.client_code,
        business_name=record.business_name,
        contact_name=record.contact_name,
        owner_name=record.owner_name,
        email=record.email,
        phone=record.phone,
        address=record.address,
        website_url=record.website_url,
        facebook_url=record.facebook_url,
        instagram_url=record.instagram_url,
        whatsapp_number=record.whatsapp_number,
        status=record.status,
        notes=record.notes,
        timezone=record.timezone,
        currency_code=record.currency_code,
        currency_symbol=record.currency_symbol,
        default_location_name=record.default_location_name,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


def _serialize_user(record: AdminUserRecord) -> AdminUserResponse:
    return AdminUserResponse(
        user_id=record.user_id,
        user_code=record.user_code,
        client_id=record.client_id,
        client_code=record.client_code,
        name=record.name,
        email=record.email,
        role_code=record.role_code,
        role_name=record.role_name,
        is_active=record.is_active,
        created_at=record.created_at.isoformat(),
        last_login_at=record.last_login_at.isoformat() if record.last_login_at else None,
        invitation_status=record.invitation_status,
        invitation_issued_at=record.invitation_issued_at.isoformat() if record.invitation_issued_at else None,
        invitation_expires_at=record.invitation_expires_at.isoformat() if record.invitation_expires_at else None,
        password_reset_issued_at=record.password_reset_issued_at.isoformat() if record.password_reset_issued_at else None,
        invitation_token=record.invitation_token,
        password_reset_token=record.password_reset_token,
        password_reset_expires_at=record.password_reset_expires_at.isoformat()
        if record.password_reset_expires_at
        else None,
    )


def _serialize_role(record: AdminRoleAccess) -> AdminRoleAccessResponse:
    return AdminRoleAccessResponse(
        role_code=record.role_code,
        role_name=record.role_name,
        description=record.description,
        allowed_pages=list(record.allowed_pages),
    )


def _serialize_audit(record: AdminAuditEntry) -> AdminAuditItemResponse:
    return AdminAuditItemResponse(
        audit_log_id=record.audit_log_id,
        client_id=record.client_id,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        action=record.action,
        actor_user_id=record.actor_user_id,
        created_at=record.created_at.isoformat(),
        metadata_json=record.metadata_json,
    )


def _serialize_onboard(result: AdminOnboardResult) -> AdminOnboardResponse:
    return AdminOnboardResponse(
        client=_serialize_client(result.client),
        users=[_serialize_user(user) for user in result.users],
        warnings=result.warnings,
    )


@router.get("/clients", response_model=AdminClientsResponse)
def list_clients(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminClientsResponse:
    _require_super_admin(user)
    items = container.admin.list_clients(search=q, status=status)
    return AdminClientsResponse(items=[_serialize_client(item) for item in items])


@router.get("/overview", response_model=ModuleOverviewResponse)
def admin_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    _require_super_admin(user)
    return container.overview.admin(user)


@router.post("/clients/onboard", response_model=AdminOnboardResponse)
def onboard_client(
    payload: AdminOnboardClientRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminOnboardResponse:
    _require_super_admin(user)
    result = container.admin.onboard_client(
        actor=user,
        request_id=getattr(request.state, "request_id", None),
        business_name=payload.business_name,
        contact_name=payload.contact_name,
        primary_email=payload.primary_email,
        primary_phone=payload.primary_phone,
        owner_name=payload.owner_name,
        owner_email=payload.owner_email,
        address=payload.address,
        website_url=payload.website_url,
        facebook_url=payload.facebook_url,
        instagram_url=payload.instagram_url,
        whatsapp_number=payload.whatsapp_number,
        notes=payload.notes,
        timezone=payload.timezone,
        currency_code=payload.currency_code,
        currency_symbol=payload.currency_symbol,
        default_location_name=payload.default_location_name,
        additional_users=[item.model_dump() for item in payload.additional_users],
    )
    return _serialize_onboard(result)


@router.get("/clients/{client_id}", response_model=AdminClientResponse)
def get_client(
    client_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminClientResponse:
    _require_super_admin(user)
    return _serialize_client(container.admin.get_client(client_id))


@router.patch("/clients/{client_id}", response_model=AdminClientResponse)
def update_client(
    client_id: str,
    payload: AdminClientUpdateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminClientResponse:
    _require_super_admin(user)
    updated = container.admin.update_client(
        client_id=client_id,
        actor=user,
        request_id=getattr(request.state, "request_id", None),
        **payload.model_dump(exclude_unset=True),
    )
    return _serialize_client(updated)


@router.get("/clients/{client_id}/users", response_model=AdminUsersResponse)
def list_client_users(
    client_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUsersResponse:
    _require_super_admin(user)
    items = container.admin.list_users(client_id)
    return AdminUsersResponse(items=[_serialize_user(item) for item in items])


@router.post("/clients/{client_id}/users", response_model=AdminUserResponse)
def create_client_user(
    client_id: str,
    payload: AdminUserCreateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserResponse:
    _require_super_admin(user)
    created = container.admin.add_user(
        client_id=client_id,
        actor=user,
        request_id=getattr(request.state, "request_id", None),
        name=payload.name,
        email=payload.email,
        role_code=payload.role_code,
    )
    return _serialize_user(created)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserResponse:
    _require_super_admin(user)
    updated = container.admin.update_user(
        user_id=user_id,
        actor=user,
        request_id=getattr(request.state, "request_id", None),
        **payload.model_dump(exclude_unset=True),
    )
    return _serialize_user(updated)


@router.post("/users/{user_id}/issue-invitation", response_model=AdminUserResponse)
def issue_invitation(
    user_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserResponse:
    _require_super_admin(user)
    issued = container.admin.issue_invitation(
        user_id=user_id,
        actor=user,
        request_id=getattr(request.state, "request_id", None),
    )
    return _serialize_user(issued)


@router.post("/users/{user_id}/issue-password-reset", response_model=AdminUserResponse)
def issue_password_reset(
    user_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserResponse:
    _require_super_admin(user)
    issued = container.admin.issue_password_reset(
        user_id=user_id,
        actor=user,
        request_id=getattr(request.state, "request_id", None),
    )
    return _serialize_user(issued)


@router.get("/roles", response_model=AdminRolesResponse)
def list_roles(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminRolesResponse:
    _require_super_admin(user)
    items = container.admin.roles()
    return AdminRolesResponse(items=[_serialize_role(item) for item in items])


@router.get("/audit", response_model=AdminAuditResponse)
def list_audit(
    client_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminAuditResponse:
    _require_super_admin(user)
    items = container.admin.audit(client_id=client_id, limit=limit)
    return AdminAuditResponse(items=[_serialize_audit(item) for item in items])
