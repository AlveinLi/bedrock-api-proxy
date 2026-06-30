"""Content audit query / detail / export endpoints."""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.core.config import settings
from app.core.timezone import parse_local_to_utc
from app.db.mysql import is_enabled as mysql_enabled

router = APIRouter()


def _require_mysql():
    if not mysql_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MySQL is not enabled; content audit requires MySQL persistence.",
        )


def _parse_window(start: Optional[str], end: Optional[str], tz_name: str):
    start_utc = parse_local_to_utc(start, tz_name) if start else None
    end_utc = parse_local_to_utc(end, tz_name) if end else None
    return start_utc, end_utc


@router.get("")
async def list_audit(
    api_key: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    user_or_owner: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    tz: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    """Paginated content audit list (oldest first), filterable by user/time."""
    _require_mysql()
    tz_name = tz or settings.app_timezone
    start_utc, end_utc = _parse_window(start, end, tz_name)

    from app.db.mysql.repositories import ContentAuditRepository

    result = ContentAuditRepository.list(
        api_key=api_key,
        user_id=user_id,
        user_or_owner=user_or_owner,
        start_utc=start_utc,
        end_utc=end_utc,
        page=page,
        page_size=page_size,
    )
    return result


@router.get("/{record_id}")
async def get_audit(record_id: int):
    """Get a single content audit record (full content)."""
    _require_mysql()
    from app.db.mysql.repositories import ContentAuditRepository

    record = ContentAuditRepository.get(record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Audit record not found"
        )
    return record


@router.get("/export/markdown")
async def export_markdown(
    api_key: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    user_or_owner: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    tz: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """Export matching content audit records as a downloadable markdown document."""
    _require_mysql()
    tz_name = tz or settings.app_timezone
    start_utc, end_utc = _parse_window(start, end, tz_name)

    from admin_portal.backend.services.markdown_export import records_to_markdown
    from app.db.mysql.repositories import ContentAuditRepository

    result = ContentAuditRepository.list(
        api_key=api_key,
        user_id=user_id,
        user_or_owner=user_or_owner,
        start_utc=start_utc,
        end_utc=end_utc,
        page=1,
        page_size=limit,
    )
    md = records_to_markdown(result["items"], tz_name, title="Content Audit Export")
    return Response(
        content=md,
        media_type="text/markdown",
        headers={
            "Content-Disposition": "attachment; filename=content-audit-export.md"
        },
    )
