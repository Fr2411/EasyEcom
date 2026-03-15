from dataclasses import replace

from fastapi import APIRouter, Depends, Response

from easy_ecom.api.dependencies import (
    ServiceContainer,
    build_session_token,
    get_authenticated_user,
    get_container,
)
from easy_ecom.api.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
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
        allowed_pages=user.allowed_pages,
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
def me(
    response: Response,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CurrentUserResponse:
    business_name = user.business_name or container.auth.get_business_name_for_client(user.client_id)
    if business_name and business_name != user.business_name:
        token = build_session_token(replace(user, business_name=business_name))
        response.set_cookie(
            key=settings.session_cookie_name,
            value=token,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            domain=settings.session_cookie_domain,
            path="/",
        )

    return CurrentUserResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        business_name=business_name,
        role=user.roles[0],
        client_id=user.client_id,
        roles=user.roles,
        allowed_pages=user.allowed_pages,
        is_authenticated=True,
    )
