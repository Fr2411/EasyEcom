from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from easy_ecom.api.middleware.request_context import RequestContextMiddleware
from easy_ecom.api.routers import api_router
from easy_ecom.core.config import settings
from easy_ecom.core.errors import http_exception_response, unexpected_exception_response

ALLOWED_WEB_ORIGIN_REGEX = r"https://(?:.*\.amplifyapp\.com|(?:www\.)?easy-ecom\.online)"


def create_app() -> FastAPI:
    app = FastAPI(title="EasyEcom API", version="0.2.0")
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_origin_regex=ALLOWED_WEB_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[settings.request_id_header],
    )
    app.add_exception_handler(HTTPException, http_exception_response)
    app.add_exception_handler(Exception, unexpected_exception_response)
    app.include_router(api_router)
    return app


app = create_app()
