from fastapi import APIRouter, Depends
from sqlalchemy.engine import Engine

from easy_ecom.api.dependencies import get_engine
from easy_ecom.core.errors import ApiException

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok", "mode": "live"}


@router.get("/health/ready")
def health_ready(engine: Engine = Depends(get_engine)) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except Exception as exc:  # pragma: no cover - defensive guard for runtime failures
        raise ApiException(
            status_code=503,
            code="READINESS_CHECK_FAILED",
            message="Database readiness check failed",
        ) from exc

    return {"status": "ok", "mode": "ready"}
