from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from easy_ecom.core.config import Settings


class Base(DeclarativeBase):
    pass


def build_postgres_engine(config: Settings) -> Engine:
    kwargs = {
        "echo": config.postgres_echo,
        "pool_pre_ping": True,
        "pool_recycle": config.postgres_pool_recycle_seconds,
    }
    if not config.postgres_dsn.startswith("sqlite"):
        kwargs["pool_size"] = config.postgres_pool_size
        kwargs["max_overflow"] = config.postgres_max_overflow
        kwargs["pool_timeout"] = config.postgres_pool_timeout_seconds
    return create_engine(config.postgres_dsn, **kwargs)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
