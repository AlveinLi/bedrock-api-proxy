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
    ensure_indexes()


def ensure_indexes() -> None:
    """Retrofit indexes that ``create_all`` cannot add to pre-existing tables.

    ``create_all`` only creates missing tables; it never alters an existing one.
    This adds the ``owner_name`` index to the content_audit table and to any
    archive tables that were created (via ``CREATE TABLE ... LIKE``) before the
    index existed. MySQL-only; other dialects (e.g. sqlite in tests) are skipped.
    """
    from sqlalchemy import text

    engine = get_engine()
    if engine.dialect.name != "mysql":
        return

    prefix = settings.mysql_table_prefix
    main_table = f"{prefix}content_audit"
    history_table = f"{prefix}content_audit_archive_history"

    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() "
                    "AND table_name LIKE :pattern AND table_name != :history"
                ),
                {"pattern": f"{main_table}%", "history": history_table},
            ).fetchall()
            tables = {r[0] for r in rows}

            for tbl in sorted(tables):
                # Skip tables that lack the owner_name column entirely.
                has_column = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() AND table_name = :t "
                        "AND column_name = 'owner_name' LIMIT 1"
                    ),
                    {"t": tbl},
                ).first()
                if not has_column:
                    continue
                # Skip if any index already covers owner_name.
                has_index = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.statistics "
                        "WHERE table_schema = DATABASE() AND table_name = :t "
                        "AND column_name = 'owner_name' LIMIT 1"
                    ),
                    {"t": tbl},
                ).first()
                if has_index:
                    continue
                conn.execute(
                    text(
                        f"ALTER TABLE `{tbl}` "
                        "ADD INDEX `ix_content_audit_owner_name` (`owner_name`)"
                    )
                )
                logger.info("Added owner_name index on %s", tbl)
    except Exception:  # pragma: no cover - best-effort migration
        logger.exception("ensure_indexes failed; owner_name index not retrofitted")
