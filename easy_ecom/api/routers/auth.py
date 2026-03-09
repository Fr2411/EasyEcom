from fastapi import APIRouter, Depends, HTTPException, Response

from easy_ecom.api.dependencies import (
    ServiceContainer,
    build_session_token,
    get_authenticated_user,
    get_container,
)
from easy_ecom.api.schemas.auth import LoginRequest, LoginResponse
from easy_ecom.core.config import settings
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, container: ServiceContainer = Depends(get_container)) -> LoginResponse:
    user = container.auth.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

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


@router.get("/me")
def me(user: AuthenticatedUser = Depends(get_authenticated_user)) -> dict[str, str | bool | None]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "role": user.roles[0] if user.roles else "",
        "client_id": user.client_id,
        "roles": user.roles,
        "is_authenticated": True,
    }
