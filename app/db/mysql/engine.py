"""MySQL engine, session management and schema initialization."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_sessionmaker: Optional[sessionmaker] = None


def is_enabled() -> bool:
    """Whether MySQL persistence is turned on."""
    return bool(settings.mysql_enabled)


def _build_url() -> str:
    if settings.mysql_dsn:
        return settings.mysql_dsn
    user = quote_plus(settings.mysql_user)
    password = quote_plus(settings.mysql_password)
    auth = f"{user}:{password}" if password else user
    return (
        f"mysql+pymysql://{auth}@{settings.mysql_host}:{settings.mysql_port}/"
        f"{settings.mysql_database}?charset=utf8mb4"
    )


def get_engine() -> Engine:
    """Return a lazily-initialized singleton SQLAlchemy engine."""
    global _engine
    if _engine is None:
        url = _build_url()
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=settings.mysql_pool_size,
            max_overflow=settings.mysql_pool_max_overflow,
            pool_recycle=3600,
            echo=settings.mysql_echo,
            future=True,
        )
        logger.info(
            "MySQL engine initialized host=%s port=%s db=%s",
            settings.mysql_host,
            settings.mysql_port,
            settings.mysql_database,
        )
    return _engine


def get_sessionmaker() -> sessionmaker:
    """Return a lazily-initialized session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = sessionmaker(
            bind=get_engine(), expire_on_commit=False, future=True
        )
    return _sessionmaker


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def table_name(base_name: str) -> str:
    """Return the prefixed table name for a logical base name."""
    return f"{settings.mysql_table_prefix}{base_name}"


def init_db() -> None:
    """Create all known tables if they do not exist.

    Importing ``models`` registers the ORM tables on the metadata.
    """
    from app.db.mysql import models  # noqa: F401  (register tables)
    from app.db.mysql.base import Base

    Base.metadata.create_all(bind=get_engine())
    logger.info("MySQL schema ensured (create_all)")
