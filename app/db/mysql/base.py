"""SQLAlchemy declarative base and shared helpers for the MySQL layer."""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all MySQL ORM models."""


def prefixed(name: str) -> str:
    """Apply the configured MySQL table prefix to a base table name."""
    return f"{settings.mysql_table_prefix}{name}"
