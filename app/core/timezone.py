"""
Timezone helpers.

Convention for the whole project:
- All timestamps are STORED in UTC (timezone-aware ``datetime`` in UTC).
- "Day" / "month" boundaries (e.g. daily token limit reset at local midnight,
  monthly budget month key) and admin-portal display are computed by converting
  UTC to a target timezone (``settings.app_timezone`` by default, or a per-request
  timezone selected in the UI).

Use these helpers everywhere instead of ``datetime.now()`` / naive datetimes so
that behaviour is consistent and testable.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings


def get_tz(tz_name: Optional[str] = None) -> ZoneInfo:
    """Return a ``ZoneInfo`` for ``tz_name`` (defaults to ``settings.app_timezone``).

    Falls back to the configured app timezone, then UTC, if an invalid name is
    supplied (never raises for runtime display paths).
    """
    name = tz_name or settings.app_timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        try:
            return ZoneInfo(settings.app_timezone)
        except (ZoneInfoNotFoundError, ValueError):
            return ZoneInfo("UTC")


def now_utc() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Return ``dt`` as timezone-aware UTC.

    Naive datetimes are assumed to already be UTC (matches DB storage convention).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_tz(dt: datetime, tz_name: Optional[str] = None) -> datetime:
    """Convert a (UTC or aware) datetime to the target timezone."""
    return ensure_utc(dt).astimezone(get_tz(tz_name))


def current_local_date(tz_name: Optional[str] = None) -> date:
    """Today's date in the target timezone."""
    return now_utc().astimezone(get_tz(tz_name)).date()


def current_month_key(tz_name: Optional[str] = None) -> str:
    """Current ``YYYY-MM`` month key in the target timezone."""
    return now_utc().astimezone(get_tz(tz_name)).strftime("%Y-%m")


def current_day_key(tz_name: Optional[str] = None) -> str:
    """Current ``YYYY-MM-DD`` day key in the target timezone."""
    return now_utc().astimezone(get_tz(tz_name)).strftime("%Y-%m-%d")


def local_date_of(dt: datetime, tz_name: Optional[str] = None) -> date:
    """Local date (in target tz) of a UTC/aware datetime."""
    return to_tz(dt, tz_name).date()


def day_bounds_utc(
    local_day: date, tz_name: Optional[str] = None
) -> Tuple[datetime, datetime]:
    """Return the [start, end) UTC bounds of a local calendar day.

    ``local_day`` is interpreted in ``tz_name``; the returned datetimes are UTC
    and suitable for ``WHERE ts >= start AND ts < end`` queries.
    """
    tz = get_tz(tz_name)
    start_local = datetime.combine(local_day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def parse_local_to_utc(value: str, tz_name: Optional[str] = None) -> datetime:
    """Parse an ISO-ish local datetime string (to the minute) into UTC.

    Accepts ``YYYY-MM-DDTHH:MM`` / ``YYYY-MM-DD HH:MM`` / with seconds, or a full
    ISO string with offset (in which case the offset wins). The value is assumed
    to be expressed in ``tz_name`` when it has no offset.
    """
    text = value.strip().replace(" ", "T")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_tz(tz_name))
    return dt.astimezone(timezone.utc)
