from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import Settings
from easy_ecom.data.store.postgres_models import Base


def build_postgres_engine(config: Settings) -> Engine:
    kwargs = {
        "echo": config.postgres_echo,
        "pool_pre_ping": True,
    }
    if not config.postgres_dsn.startswith("sqlite"):
        kwargs["pool_size"] = config.postgres_pool_size
        kwargs["max_overflow"] = config.postgres_max_overflow
    return create_engine(config.postgres_dsn, **kwargs)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_postgres_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
