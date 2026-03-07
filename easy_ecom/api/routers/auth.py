from fastapi import APIRouter, Depends, HTTPException

from easy_ecom.api.dependencies import ServiceContainer, get_container
from easy_ecom.api.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, container: ServiceContainer = Depends(get_container)) -> LoginResponse:
    user = container.users.login(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return LoginResponse(**user)
