"""Content audit history / archiving endpoints.

Provides:
- Info about the content audit table (total rows, earliest date, age in days).
- Asynchronous archiving of rows older than N days into a timestamped table.
- Query of archive history (by overlapping data window) and of archive tables.
"""
import sys
import threading
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.timezone import now_utc, parse_local_to_utc, to_tz
from app.db.mysql import is_enabled as mysql_enabled

router = APIRouter()


class ArchiveRequest(BaseModel):
    keep_days: int = Field(..., gt=0, description="Number of most-recent days to keep")
    tz: Optional[str] = Field(default=None, description="Timezone for day boundary")


def _require_mysql():
    if not mysql_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MySQL is not enabled; content audit history requires MySQL persistence.",
        )


@router.get("/info")
async def audit_info(tz: Optional[str] = Query(default=None)):
    """Total rows, earliest request time, and days since earliest."""
    _require_mysql()
    tz_name = tz or settings.app_timezone
    from app.db.mysql.repositories import ContentAuditRepository

    info = ContentAuditRepository.info()
    earliest = info.get("earliest_request_time")
    days_since = None
    earliest_local = None
    if earliest is not None:
        delta = now_utc() - earliest.replace(tzinfo=now_utc().tzinfo)
        days_since = max(delta.days, 0)
        earliest_local = to_tz(earliest, tz_name).strftime("%Y-%m-%d %H:%M:%S %Z")
    return {
        "total": info.get("total", 0),
        "earliest_request_time": earliest_local,
        "days_since_earliest": days_since,
        "timezone": tz_name,
    }


@router.post("/archive")
async def start_archive_task(request: ArchiveRequest):
    """Start an asynchronous archive of rows older than ``keep_days`` days."""
    _require_mysql()
    tz_name = request.tz or settings.app_timezone

    from app.db.mysql.archive import run_archive, start_archive

    history_id = start_archive(request.keep_days, tz_name)

    thread = threading.Thread(
        target=run_archive,
        args=(history_id, tz_name),
        name=f"content-audit-archive-{history_id}",
        daemon=True,
    )
    thread.start()

    from app.db.mysql.repositories import ArchiveHistoryRepository

    row = ArchiveHistoryRepository.get(history_id)
    return {
        "task_id": history_id,
        "archive_table_name": row.get("archive_table_name") if row else None,
        "status": row.get("status") if row else "running",
    }


@router.get("/archive/status/{task_id}")
async def archive_status(task_id: int):
    """Poll the status of an archive task."""
    _require_mysql()
    from app.db.mysql.repositories import ArchiveHistoryRepository

    row = ArchiveHistoryRepository.get(task_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Archive task not found"
        )
    return row


@router.get("/history")
async def archive_history(
    start: str = Query(..., description="Local start datetime (to the minute)"),
    end: str = Query(..., description="Local end datetime (to the minute)"),
    tz: Optional[str] = Query(default=None),
):
    """Archive history whose data window overlaps [start, end].

    Overlap condition: data_start_time <= end AND data_end_time >= start.
    Ordered by archive_time DESC.
    """
    _require_mysql()
    tz_name = tz or settings.app_timezone
    start_utc = parse_local_to_utc(start, tz_name)
    end_utc = parse_local_to_utc(end, tz_name)

    from app.db.mysql.repositories import ArchiveHistoryRepository

    rows = ArchiveHistoryRepository.query_overlapping(start_utc, end_utc)
    return {"items": rows, "count": len(rows)}


@router.get("/archive/{archive_table}/records")
async def archive_records(
    archive_table: str,
    api_key: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    tz: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """Query records inside a specific archive table (same shape as content audit)."""
    _require_mysql()
    tz_name = tz or settings.app_timezone
    start_utc = parse_local_to_utc(start, tz_name) if start else None
    end_utc = parse_local_to_utc(end, tz_name) if end else None

    from app.db.mysql.archive import query_archive_table

    try:
        return query_archive_table(
            archive_table,
            api_key=api_key,
            user_id=user_id,
            start_utc=start_utc,
            end_utc=end_utc,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/archive/{archive_table}/records/{record_id}")
async def archive_record_detail(archive_table: str, record_id: int):
    """Get a single record from an archive table."""
    _require_mysql()
    from app.db.mysql.archive import get_archive_row

    try:
        row = get_archive_row(archive_table, record_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Archive record not found"
        )
    return row


@router.get("/archive/{archive_table}/export/markdown")
async def export_archive_markdown(
    archive_table: str,
    api_key: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    tz: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """Export an archive table's matching records as a markdown document."""
    _require_mysql()
    tz_name = tz or settings.app_timezone
    start_utc = parse_local_to_utc(start, tz_name) if start else None
    end_utc = parse_local_to_utc(end, tz_name) if end else None

    from admin_portal.backend.services.markdown_export import records_to_markdown
    from app.db.mysql.archive import query_archive_table

    try:
        result = query_archive_table(
            archive_table,
            api_key=api_key,
            user_id=user_id,
            start_utc=start_utc,
            end_utc=end_utc,
            page=1,
            page_size=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    md = records_to_markdown(result["items"], tz_name, title=f"Archive Export: {archive_table}")
    return Response(
        content=md,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={archive_table}-export.md"
        },
    )
