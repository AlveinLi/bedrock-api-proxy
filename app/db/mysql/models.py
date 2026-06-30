"""SQLAlchemy ORM models for the MySQL persistence layer.

All datetime columns store UTC. Display/day-boundary conversions are done by
``app.core.timezone`` using the selected/app timezone.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timezone import now_utc
from app.db.mysql.base import Base, prefixed

# Portable "very large text" type: LONGTEXT on MySQL, TEXT elsewhere (tests/sqlite).
LongText = Text().with_variant(LONGTEXT, "mysql")

# Autoincrement primary key: BIGINT on MySQL, INTEGER on SQLite (SQLite only
# auto-increments INTEGER PRIMARY KEY, not BIGINT) so tests can use SQLite.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class ApiKeyRecord(Base):
    """Master store for API keys and their configuration (synced to DynamoDB)."""

    __tablename__ = prefixed("api_keys")

    api_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rate_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)

    monthly_budget: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    budget_used: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    budget_used_mtd: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    budget_mtd_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    budget_history: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Daily token limit. Stored in units of 万 (10k tokens); 0 = unlimited.
    daily_token_limit: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    daily_tokens_used: Mapped[int] = mapped_column(BigInteger, default=0)
    daily_tokens_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    deactivated_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cache_ttl: Mapped[str | None] = mapped_column(String(16), nullable=True)
    routing_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    compression_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, onupdate=now_utc
    )


class UsageDetail(Base):
    """Per-request token usage detail (mirrors DynamoDB usage table + cost)."""

    __tablename__ = prefixed("usage_detail")

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    api_key: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(255), index=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_surface: Mapped[str | None] = mapped_column(String(32), nullable=True)
    service_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)

    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cost: Mapped[float] = mapped_column(Numeric(18, 8), default=0)

    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    request_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    __table_args__ = (
        Index("ix_usage_detail_key_time", "api_key", "request_time"),
    )


class ContentAudit(Base):
    """Full request/response content for auditing (independent of OTEL)."""

    __tablename__ = prefixed("content_audit")

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    api_key: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(255), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    request_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_surface: Mapped[str | None] = mapped_column(String(32), nullable=True)
    service_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(LongText, nullable=True)
    request_messages: Mapped[str | None] = mapped_column(LongText, nullable=True)
    tools: Mapped[str | None] = mapped_column(LongText, nullable=True)
    response_content: Mapped[str | None] = mapped_column(LongText, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    streaming: Mapped[bool] = mapped_column(Boolean, default=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cost: Mapped[float] = mapped_column(Numeric(18, 8), default=0)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    __table_args__ = (
        Index("ix_content_audit_key_time", "api_key", "request_time"),
    )


class ContentAuditArchiveHistory(Base):
    """History of content-audit archive operations."""

    __tablename__ = prefixed("content_audit_archive_history")

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    archive_time: Mapped[datetime] = mapped_column(DateTime, index=True, default=now_utc)
    archive_table_name: Mapped[str] = mapped_column(String(128))
    record_count: Mapped[int] = mapped_column(BigInteger, default=0)
    data_start_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    data_end_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    duration_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running")
    keep_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cutoff_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
