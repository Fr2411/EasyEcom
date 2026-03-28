from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.api.middleware.request_context import RequestContextMiddleware
from easy_ecom.api.routers import api_router
from easy_ecom.core.config import settings
from easy_ecom.core.errors import http_exception_response, unexpected_exception_response
from easy_ecom.data.store.postgres_db import build_session_factory
from easy_ecom.data.store.runtime import build_runtime_engine

ALLOWED_WEB_ORIGIN_REGEX = r"https://(?:.*\.amplifyapp\.com|(?:www\.)?easy-ecom\.online)"


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = getattr(app.state, "db_engine", None)
    session_factory = getattr(app.state, "db_session_factory", None)
    owns_engine = engine is None or session_factory is None
    if owns_engine:
        engine = build_runtime_engine(settings)
        session_factory = build_session_factory(engine)
        app.state.db_engine = engine
        app.state.db_session_factory = session_factory
    try:
        yield
    finally:
        if owns_engine:
            engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="EasyEcom API", version="0.2.0", lifespan=lifespan)
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
