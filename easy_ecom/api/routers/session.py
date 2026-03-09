from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import get_authenticated_user
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/me")
def session_me(user: AuthenticatedUser = Depends(get_authenticated_user)) -> dict[str, str | bool | None]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "role": user.roles[0] if user.roles else "",
        "client_id": user.client_id,
        "is_authenticated": True,
    }
