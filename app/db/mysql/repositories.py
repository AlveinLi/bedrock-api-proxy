"""Repository helpers for the MySQL persistence layer.

These wrap common read/write operations on the ORM models. The proxy runtime
uses the write paths (usage detail, content audit); the admin portal uses the
query/aggregation paths.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from app.db.mysql.engine import session_scope
from app.db.mysql.models import (
    ApiKeyRecord,
    ContentAudit,
    ContentAuditArchiveHistory,
    UsageDetail,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _row_to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# --------------------------------------------------------------------------- #
# API key master store
# --------------------------------------------------------------------------- #
class ApiKeyRepository:
    """CRUD for the API key master store (source of truth, synced to DynamoDB)."""

    # Columns that are settable from a dict payload.
    _COLUMNS = {c.name for c in ApiKeyRecord.__table__.columns}

    @classmethod
    def upsert(cls, data: Dict[str, Any]) -> None:
        api_key = data.get("api_key")
        if not api_key:
            raise ValueError("api_key is required for upsert")
        payload = {k: v for k, v in data.items() if k in cls._COLUMNS}
        with session_scope() as session:
            existing = session.get(ApiKeyRecord, api_key)
            if existing:
                for k, v in payload.items():
                    if k in ("api_key", "created_at"):
                        continue
                    setattr(existing, k, v)
            else:
                session.add(ApiKeyRecord(**payload))

    @classmethod
    def get(cls, api_key: str) -> Optional[Dict[str, Any]]:
        with session_scope() as session:
            obj = session.get(ApiKeyRecord, api_key)
            return _row_to_dict(obj) if obj else None

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(select(ApiKeyRecord)).scalars().all()
            return [_row_to_dict(r) for r in rows]

    @classmethod
    def delete(cls, api_key: str) -> bool:
        with session_scope() as session:
            obj = session.get(ApiKeyRecord, api_key)
            if not obj:
                return False
            session.delete(obj)
            return True

    @classmethod
    def set_fields(cls, api_key: str, **fields: Any) -> bool:
        payload = {k: v for k, v in fields.items() if k in cls._COLUMNS}
        if not payload:
            return False
        with session_scope() as session:
            obj = session.get(ApiKeyRecord, api_key)
            if not obj:
                return False
            for k, v in payload.items():
                setattr(obj, k, v)
            return True


# --------------------------------------------------------------------------- #
# Usage detail
# --------------------------------------------------------------------------- #
class UsageDetailRepository:
    _COLUMNS = {c.name for c in UsageDetail.__table__.columns}

    @classmethod
    def insert(cls, data: Dict[str, Any]) -> None:
        payload = {k: v for k, v in data.items() if k in cls._COLUMNS}
        with session_scope() as session:
            session.add(UsageDetail(**payload))

    @classmethod
    def sum_tokens_in_range(
        cls, api_key: str, start_utc: datetime, end_utc: datetime
    ) -> int:
        """Sum total_tokens for a key over [start, end) (used for daily limit checks)."""
        with session_scope() as session:
            stmt = (
                select(func.coalesce(func.sum(UsageDetail.total_tokens), 0))
                .where(UsageDetail.api_key == api_key)
                .where(UsageDetail.request_time >= start_utc)
                .where(UsageDetail.request_time < end_utc)
            )
            return int(session.execute(stmt).scalar_one() or 0)

    @classmethod
    def aggregate_by_key(
        cls, start_utc: datetime, end_utc: datetime
    ) -> List[Dict[str, Any]]:
        """Aggregate usage metrics grouped by api_key over [start, end)."""
        with session_scope() as session:
            stmt = (
                select(
                    UsageDetail.api_key,
                    func.coalesce(func.sum(UsageDetail.input_tokens), 0).label("input_tokens"),
                    func.coalesce(func.sum(UsageDetail.output_tokens), 0).label("output_tokens"),
                    func.coalesce(func.sum(UsageDetail.cache_read_tokens), 0).label("cache_read_tokens"),
                    func.coalesce(func.sum(UsageDetail.cache_write_tokens), 0).label("cache_write_tokens"),
                    func.coalesce(func.sum(UsageDetail.total_tokens), 0).label("total_tokens"),
                    func.count(UsageDetail.id).label("requests"),
                    func.coalesce(func.sum(UsageDetail.cost), 0).label("total_cost"),
                )
                .where(UsageDetail.request_time >= start_utc)
                .where(UsageDetail.request_time < end_utc)
                .group_by(UsageDetail.api_key)
            )
            result = []
            for row in session.execute(stmt).mappings().all():
                d = dict(row)
                d["total_cost"] = float(d["total_cost"] or 0)
                result.append(d)
            return result


# --------------------------------------------------------------------------- #
# Content audit
# --------------------------------------------------------------------------- #
class ContentAuditRepository:
    _COLUMNS = {c.name for c in ContentAudit.__table__.columns}

    @classmethod
    def insert(cls, data: Dict[str, Any]) -> None:
        payload = {k: v for k, v in data.items() if k in cls._COLUMNS}
        with session_scope() as session:
            session.add(ContentAudit(**payload))

    @classmethod
    def list(
        cls,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        start_utc: Optional[datetime] = None,
        end_utc: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Paginated list (newest first). Returns {items, total, page, page_size}."""
        with session_scope() as session:
            conditions = []
            if api_key:
                conditions.append(ContentAudit.api_key == api_key)
            if user_id:
                conditions.append(ContentAudit.user_id == user_id)
            if start_utc:
                conditions.append(ContentAudit.request_time >= start_utc)
            if end_utc:
                conditions.append(ContentAudit.request_time < end_utc)

            count_stmt = select(func.count(ContentAudit.id))
            for c in conditions:
                count_stmt = count_stmt.where(c)
            total = int(session.execute(count_stmt).scalar_one() or 0)

            stmt = select(ContentAudit)
            for c in conditions:
                stmt = stmt.where(c)
            stmt = (
                stmt.order_by(ContentAudit.request_time.desc(), ContentAudit.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            items = [_row_to_dict(r) for r in session.execute(stmt).scalars().all()]
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    @classmethod
    def get(cls, record_id: int) -> Optional[Dict[str, Any]]:
        with session_scope() as session:
            obj = session.get(ContentAudit, record_id)
            return _row_to_dict(obj) if obj else None

    @classmethod
    def info(cls) -> Dict[str, Any]:
        """Total count and earliest request_time in the content audit table."""
        with session_scope() as session:
            total = int(
                session.execute(select(func.count(ContentAudit.id))).scalar_one() or 0
            )
            earliest = session.execute(
                select(func.min(ContentAudit.request_time))
            ).scalar_one()
            return {"total": total, "earliest_request_time": earliest}


# --------------------------------------------------------------------------- #
# Archive history
# --------------------------------------------------------------------------- #
class ArchiveHistoryRepository:
    @classmethod
    def create(cls, data: Dict[str, Any]) -> int:
        with session_scope() as session:
            row = ContentAuditArchiveHistory(**data)
            session.add(row)
            session.flush()
            return int(row.id)

    @classmethod
    def update(cls, record_id: int, **fields: Any) -> None:
        with session_scope() as session:
            obj = session.get(ContentAuditArchiveHistory, record_id)
            if obj:
                for k, v in fields.items():
                    setattr(obj, k, v)

    @classmethod
    def get(cls, record_id: int) -> Optional[Dict[str, Any]]:
        with session_scope() as session:
            obj = session.get(ContentAuditArchiveHistory, record_id)
            return _row_to_dict(obj) if obj else None

    @classmethod
    def query_overlapping(
        cls, start_utc: datetime, end_utc: datetime
    ) -> List[Dict[str, Any]]:
        """Archives whose data window overlaps [start, end].

        Condition: data_start_time <= end AND data_end_time >= start.
        Ordered by archive_time DESC.
        """
        with session_scope() as session:
            stmt = (
                select(ContentAuditArchiveHistory)
                .where(ContentAuditArchiveHistory.data_start_time <= end_utc)
                .where(ContentAuditArchiveHistory.data_end_time >= start_utc)
                .order_by(ContentAuditArchiveHistory.archive_time.desc())
            )
            return [_row_to_dict(r) for r in session.execute(stmt).scalars().all()]
