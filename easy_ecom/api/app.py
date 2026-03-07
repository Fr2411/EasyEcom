from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from easy_ecom.api.routers import api_router
from easy_ecom.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="EasyEcom API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_origin_regex=r"https://.*\.amplifyapp\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
