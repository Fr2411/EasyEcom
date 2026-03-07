from fastapi import APIRouter

from easy_ecom.api.routers.health import router as health_router
from easy_ecom.api.routers.session import router as session_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(session_router)
