from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import RequestUser, get_current_user

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/me")
def session_me(user: RequestUser = Depends(get_current_user)) -> dict[str, str | list[str]]:
    return {
        "user_id": user.user_id,
        "client_id": user.client_id,
        "roles": user.roles,
    }
