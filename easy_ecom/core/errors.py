from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class ErrorEnvelope:
    code: str
    message: str
    request_id: str | None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
        }
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


class ApiException(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def http_exception_response(request: Request, exc: HTTPException) -> JSONResponse:
    code = getattr(exc, "code", "http_error").upper()
    message = getattr(exc, "message", str(exc.detail))
    details = getattr(exc, "details", None)
    envelope = ErrorEnvelope(
        code=code,
        message=message,
        request_id=_request_id(request),
        details=details,
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.as_dict())


def unexpected_exception_response(request: Request, exc: Exception) -> JSONResponse:
    envelope = ErrorEnvelope(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred.",
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=500, content=envelope.as_dict())
