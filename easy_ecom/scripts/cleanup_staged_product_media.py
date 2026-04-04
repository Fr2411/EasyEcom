from __future__ import annotations

from easy_ecom.core.config import settings
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.domain.services.product_media_service import ProductMediaService


def main() -> None:
    engine = build_postgres_engine(settings)
    session_factory = build_session_factory(engine)
    service = ProductMediaService()
    with session_factory() as session:
        removed = service.cleanup_expired_staged_uploads(session)
        session.commit()
    print(f"Removed {removed} expired staged product media uploads.")


if __name__ == "__main__":
    main()
