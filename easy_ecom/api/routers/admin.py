from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from easy_ecom.api.dependencies import (
    RequestUser,
    ServiceContainer,
    get_container,
    get_current_user,
)
from easy_ecom.api.schemas.admin import (
    AdminAuditResponse,
    AdminCreateTenantRequest,
    AdminCreateUserRequest,
    AdminRolesResponse,
    AdminSetRolesRequest,
    AdminTenantCreateResponse,
    AdminUpdateUserRequest,
    AdminUserMutationResponse,
    AdminUserRecord,
    AdminUsersResponse,
)
from easy_ecom.core.rbac import ADMIN_MANAGE_USERS_ROLES, has_any_role
from easy_ecom.domain.services.admin_api_service import DEFAULT_ROLE_CODES

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin_access(user: RequestUser) -> None:
    if not user.client_id:
        raise HTTPException(status_code=401, detail="Invalid tenant context")
    if not has_any_role(user.roles, ADMIN_MANAGE_USERS_ROLES):
        raise HTTPException(status_code=403, detail="Admin access required")


def _require_container_admin(container: ServiceContainer):
    if container.admin is None:
        raise HTTPException(status_code=503, detail="Admin APIs require postgres backend")
    return container.admin


def _to_schema_user(item) -> AdminUserRecord:
    return AdminUserRecord(
        user_id=item.user_id,
        client_id=item.client_id,
        name=item.name,
        email=item.email,
        is_active=item.is_active,
        created_at=item.created_at,
        roles=item.roles,
    )


@router.get("/users", response_model=AdminUsersResponse)
def list_users(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUsersResponse:
    _require_admin_access(user)
    admin = _require_container_admin(container)
    records = sorted(
        admin.list_users_for_client(client_id=user.client_id), key=lambda item: item.name.lower()
    )
    return AdminUsersResponse(items=[_to_schema_user(item) for item in records])


@router.post("/tenants", response_model=AdminTenantCreateResponse, status_code=201)
def create_tenant(
    payload: AdminCreateTenantRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminTenantCreateResponse:
    _require_admin_access(user)
    if "SUPER_ADMIN" not in user.roles:
        raise HTTPException(status_code=403, detail="Only super admin can create new tenants")
    admin = _require_container_admin(container)
    try:
        created = admin.create_tenant_with_owner(
            business_name=payload.business_name,
            owner_name=payload.owner_name,
            owner_email=payload.owner_email,
            owner_password=payload.owner_password,
            currency_code=payload.currency_code,
            owner_role_codes=["CLIENT_OWNER"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AdminTenantCreateResponse(
        client_id=created.client_id,
        business_name=created.business_name,
        owner_user=_to_schema_user(created.owner_user),
    )


@router.post("/users", response_model=AdminUserMutationResponse, status_code=201)
def create_user(
    payload: AdminCreateUserRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserMutationResponse:
    _require_admin_access(user)
    admin = _require_container_admin(container)
    if "SUPER_ADMIN" in payload.role_codes and "SUPER_ADMIN" not in user.roles:
        raise HTTPException(status_code=403, detail="Only super admin can assign SUPER_ADMIN role")
    target_client_id = user.client_id
    if "SUPER_ADMIN" in user.roles and payload.client_id:
        target_client_id = payload.client_id.strip()
    elif payload.client_id and payload.client_id.strip() != user.client_id:
        raise HTTPException(status_code=403, detail="Cannot assign user to a different tenant")

    try:
        created = admin.create_user(
            client_id=target_client_id,
            name=payload.name,
            email=payload.email,
            password=payload.password,
            role_codes=payload.role_codes,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AdminUserMutationResponse(user=_to_schema_user(created))


@router.get("/users/{user_id}", response_model=AdminUserMutationResponse)
def get_user(
    user_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserMutationResponse:
    _require_admin_access(user)
    admin = _require_container_admin(container)
    record = admin.get_user_for_client(client_id=user.client_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserMutationResponse(user=_to_schema_user(record))


@router.patch("/users/{user_id}", response_model=AdminUserMutationResponse)
def update_user(
    user_id: str,
    payload: AdminUpdateUserRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserMutationResponse:
    _require_admin_access(user)
    admin = _require_container_admin(container)
    if user_id == user.user_id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if not payload.model_dump(exclude_none=True):
        raise HTTPException(status_code=400, detail="No fields provided")
    try:
        updated = admin.update_user_profile(
            client_id=user.client_id,
            user_id=user_id,
            name=payload.name,
            email=payload.email,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserMutationResponse(user=_to_schema_user(updated))


@router.get("/roles", response_model=AdminRolesResponse)
def list_roles(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminRolesResponse:
    _require_admin_access(user)
    _ = _require_container_admin(container)
    return AdminRolesResponse(roles=DEFAULT_ROLE_CODES)


@router.patch("/users/{user_id}/roles", response_model=AdminUserMutationResponse)
def set_user_roles(
    user_id: str,
    payload: AdminSetRolesRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminUserMutationResponse:
    _require_admin_access(user)
    admin = _require_container_admin(container)

    if user_id == user.user_id and "SUPER_ADMIN" not in payload.role_codes:
        raise HTTPException(status_code=400, detail="You cannot remove your own super-admin role")

    if "SUPER_ADMIN" in payload.role_codes and "SUPER_ADMIN" not in user.roles:
        raise HTTPException(status_code=403, detail="Only super admin can assign SUPER_ADMIN role")

    updated = admin.set_user_roles(
        client_id=user.client_id, user_id=user_id, role_codes=payload.role_codes
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return AdminUserMutationResponse(user=_to_schema_user(updated))


@router.get("/audit", response_model=AdminAuditResponse)
def admin_audit(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> AdminAuditResponse:
    _require_admin_access(user)
    _ = _require_container_admin(container)
    return AdminAuditResponse(
        supported=False,
        deferred_reason="Tenant-scoped Postgres audit event stream is not implemented yet.",
        items=[],
    )
