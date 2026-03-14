from fastapi import APIRouter, Depends, Response, status

from easy_ecom.api.dependencies import (
    ServiceContainer,
    build_session_token,
    get_authenticated_user,
    get_container,
)
from easy_ecom.api.schemas.auth import (
    AcceptInvitationRequest,
    CurrentUserResponse,
    InvitationIssueRequest,
    InvitationIssueResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetConfirmRequest,
    PasswordResetIssueResponse,
    PasswordResetRequest,
)
from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, container: ServiceContainer = Depends(get_container)) -> LoginResponse:
    user = container.auth.authenticate(payload.email.strip().lower(), payload.password)
    if not user:
        raise ApiException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid credentials",
        )

    token = build_session_token(user)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain,
        path="/",
    )
    return LoginResponse(
        user_id=user.user_id,
        client_id=user.client_id,
        roles=user.roles_csv,
        name=user.name,
        email=user.email,
    )


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.session_cookie_domain,
        path="/",
    )
    return {"success": True}


@router.get("/me", response_model=CurrentUserResponse)
def me(user: AuthenticatedUser = Depends(get_authenticated_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        role=user.roles[0],
        client_id=user.client_id,
        roles=user.roles,
        is_authenticated=True,
    )


@router.post(
    "/request-password-reset",
    response_model=PasswordResetIssueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_reset(
    payload: PasswordResetRequest,
    container: ServiceContainer = Depends(get_container),
) -> PasswordResetIssueResponse:
    issued = container.auth.issue_password_reset(
        payload.email.strip().lower(),
        settings.password_reset_ttl_minutes,
    )
    if issued is None:
        return PasswordResetIssueResponse(accepted=True, delivery="manual")
    return PasswordResetIssueResponse(
        accepted=True,
        delivery="manual",
        reset_token=issued.plain_token if settings.app_env != "production" else None,
        expires_at=issued.expires_at.isoformat(),
    )


@router.post("/reset-password")
def reset_password(
    payload: PasswordResetConfirmRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict[str, bool]:
    success = container.auth.reset_password(payload.token.strip(), payload.new_password)
    if not success:
        raise ApiException(
            status_code=400,
            code="INVALID_RESET_TOKEN",
            message="Password reset token is invalid or expired",
        )
    return {"success": True}


@router.post("/accept-invitation", response_model=LoginResponse)
def accept_invitation(
    payload: AcceptInvitationRequest,
    response: Response,
    container: ServiceContainer = Depends(get_container),
) -> LoginResponse:
    user = container.auth.accept_invitation(
        payload.token.strip(),
        payload.name,
        payload.password,
    )
    if not user:
        raise ApiException(
            status_code=400,
            code="INVALID_INVITATION",
            message="Invitation token is invalid or expired",
        )

    session_token = build_session_token(user)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain,
        path="/",
    )
    return LoginResponse(
        user_id=user.user_id,
        client_id=user.client_id,
        roles=user.roles_csv,
        name=user.name,
        email=user.email,
    )


@router.post("/issue-invitation", response_model=InvitationIssueResponse)
def issue_invitation(
    payload: InvitationIssueRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> InvitationIssueResponse:
    if "SUPER_ADMIN" not in user.roles:
        raise ApiException(
            status_code=403,
            code="ACCESS_DENIED",
            message="Only super admins can issue invitations",
        )

    target_client_id = payload.client_id.strip()
    issued = container.auth.issue_invitation(
        client_id=target_client_id,
        email=payload.email.strip().lower(),
        role_code=payload.role_code.strip().upper(),
        invited_by_user_id=user.user_id,
        ttl_hours=settings.invitation_ttl_hours,
    )
    return InvitationIssueResponse(
        invitation_id=issued.record_id,
        invitation_token=issued.plain_token,
        expires_at=issued.expires_at.isoformat(),
    )
