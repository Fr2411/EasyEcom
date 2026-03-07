from fastapi import APIRouter

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/me")
def session_me() -> dict[str, str | bool | None]:
    return {
        "user_id": "dev-super-admin",
        "email": "admin@easyecom.local",
        "name": "Super Admin",
        "role": "SUPER_ADMIN",
        "client_id": None,
        "is_authenticated": True,
    }
