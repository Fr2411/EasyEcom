from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from easy_ecom.core.config import settings


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(settings.request_id_header) or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[settings.request_id_header] = request_id
        return response
