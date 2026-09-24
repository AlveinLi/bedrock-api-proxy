"""Content audit archiving.

Moves old rows out of the content audit table into a timestamped archive table
and records the operation in the archive history table. Also supports querying
archive tables (same shape as the content audit table).

Archive tables are named ``<prefix>content_audit_<YYYYMMDDHHMM>`` where the prefix
matches the content audit table's prefix.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.core.timezone import current_local_date, day_bounds_utc, now_utc
from app.db.mysql.engine import get_engine, table_name
from app.db.mysql.repositories import ArchiveHistoryRepository

logger = logging.getLogger(__name__)

_CONTENT_AUDIT_TABLE = table_name("content_audit")
_ARCHIVE_TABLE_RE = re.compile(
    rf"^{re.escape(_CONTENT_AUDIT_TABLE)}_\d{{12}}$"
)


def is_valid_archive_table(name: str) -> bool:
    """Whether ``name`` is a valid content-audit archive table name."""
    return bool(_ARCHIVE_TABLE_RE.match(name))


def compute_cutoff_utc(keep_days: int, tz_name: Optional[str] = None):
    """Return the UTC cutoff datetime; rows strictly before it get archived.

    Follows the spec: cutoff_date = today_local - keep_days; archive rows whose
    request_time is earlier than the start of that local day.
    """
    today_local = current_local_date(tz_name)
    cutoff_date = today_local - timedelta(days=keep_days)
    cutoff_start_utc, _ = day_bounds_utc(cutoff_date, tz_name)
    return cutoff_start_utc


def start_archive(keep_days: int, tz_name: Optional[str] = None) -> int:
    """Create a 'running' archive history row and return its id (task id)."""
    cutoff_utc = compute_cutoff_utc(keep_days, tz_name)
    suffix = now_utc().astimezone(_local_tz(tz_name)).strftime("%Y%m%d%H%M")
    archive_table = f"{_CONTENT_AUDIT_TABLE}_{suffix}"
    return ArchiveHistoryRepository.create(
        {
            "archive_time": now_utc(),
            "archive_table_name": archive_table,
            "record_count": 0,
            "status": "running",
            "keep_days": keep_days,
            "cutoff_time": cutoff_utc,
        }
    )


def _local_tz(tz_name: Optional[str]):
    from app.core.timezone import get_tz

    return get_tz(tz_name)


def run_archive(history_id: int, tz_name: Optional[str] = None) -> None:
    """Execute the archive operation for a previously created history row.

    Intended to run on a background thread.
    """
    started = time.perf_counter()
    history = ArchiveHistoryRepository.get(history_id)
    if not history:
        logger.error("Archive history %s not found", history_id)
        return

    archive_table = history["archive_table_name"]
    cutoff_utc = history["cutoff_time"]

    if not is_valid_archive_table(archive_table):
        ArchiveHistoryRepository.update(
            history_id, status="failed", error_message="Invalid archive table name"
        )
        return

    engine = get_engine()
    try:
        with engine.begin() as conn:
            # Create the archive table with the same structure
            conn.execute(
                text(f"CREATE TABLE IF NOT EXISTS `{archive_table}` LIKE `{_CONTENT_AUDIT_TABLE}`")
            )

            # Compute the window of data being moved (min/max request_time, count)
            stats = conn.execute(
                text(
                    f"SELECT COUNT(*) AS cnt, MIN(request_time) AS min_t, MAX(request_time) AS max_t "
                    f"FROM `{_CONTENT_AUDIT_TABLE}` WHERE request_time < :cutoff"
                ),
                {"cutoff": cutoff_utc},
            ).mappings().first()

            count = int(stats["cnt"] or 0)
            data_start = stats["min_t"]
            data_end = stats["max_t"]

            if count > 0:
                # Move rows: copy then delete (same transaction)
                conn.execute(
                    text(
                        f"INSERT INTO `{archive_table}` "
                        f"SELECT * FROM `{_CONTENT_AUDIT_TABLE}` WHERE request_time < :cutoff"
                    ),
                    {"cutoff": cutoff_utc},
                )
                conn.execute(
                    text(
                        f"DELETE FROM `{_CONTENT_AUDIT_TABLE}` WHERE request_time < :cutoff"
                    ),
                    {"cutoff": cutoff_utc},
                )

        duration_ms = int((time.perf_counter() - started) * 1000)
        ArchiveHistoryRepository.update(
            history_id,
            status="done",
            record_count=count,
            data_start_time=data_start,
            data_end_time=data_end,
            duration_ms=duration_ms,
        )
        logger.info(
            "Archived %d content audit rows into %s (%.0f ms)",
            count,
            archive_table,
            duration_ms,
        )
    except Exception as exc:
        logger.error("Archive operation failed: %s", exc)
        ArchiveHistoryRepository.update(
            history_id,
            status="failed",
            error_message=str(exc),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


def query_archive_table(
    archive_table: str,
    api_key: Optional[str] = None,
    user_id: Optional[str] = None,
    start_utc=None,
    end_utc=None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Paginated query over an archive table (same shape as content audit)."""
    if not is_valid_archive_table(archive_table):
        raise ValueError("Invalid archive table name")

    where = []
    params: Dict[str, Any] = {}
    if api_key:
        where.append("api_key = :api_key")
        params["api_key"] = api_key
    if user_id:
        where.append("user_id = :user_id")
        params["user_id"] = user_id
    if start_utc is not None:
        where.append("request_time >= :start")
        params["start"] = start_utc
    if end_utc is not None:
        where.append("request_time < :end")
        params["end"] = end_utc
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    engine = get_engine()
    with engine.connect() as conn:
        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM `{archive_table}`{where_sql}"), params
            ).scalar_one()
            or 0
        )
        rows_params = dict(params)
        rows_params["limit"] = page_size
        rows_params["offset"] = (page - 1) * page_size
        result = conn.execute(
            text(
                f"SELECT * FROM `{archive_table}`{where_sql} "
                f"ORDER BY request_time DESC, id DESC LIMIT :limit OFFSET :offset"
            ),
            rows_params,
        ).mappings().all()
        items: List[Dict[str, Any]] = [dict(r) for r in result]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_archive_row(archive_table: str, record_id: int) -> Optional[Dict[str, Any]]:
    if not is_valid_archive_table(archive_table):
        raise ValueError("Invalid archive table name")
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(f"SELECT * FROM `{archive_table}` WHERE id = :id"),
            {"id": record_id},
        ).mappings().first()
        return dict(row) if row else None
