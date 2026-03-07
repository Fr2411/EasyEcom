from fastapi import APIRouter

from easy_ecom.api.routers.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
