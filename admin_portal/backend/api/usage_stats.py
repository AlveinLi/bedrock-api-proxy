"""Usage statistics by time range (per-user aggregation).

Aggregated metrics (input/output/cache read/cache write/total tokens/requests/
total cost) are summed from MySQL ``proxy_usage_detail`` over the selected time
window. The remaining fields (owner, daily limit, monthly budget, service tier)
are per-user configuration attributes taken from the API key store (not summed).
"""
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.core.timezone import day_bounds_utc, parse_local_to_utc
from app.db.dynamodb import APIKeyManager, DynamoDBClient
from app.db.mysql import is_enabled as mysql_enabled

router = APIRouter()


def _require_mysql():
    if not mysql_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MySQL is not enabled; usage statistics require MySQL persistence.",
        )


def _key_config_map() -> dict:
    """Map api_key -> config attributes (owner, daily limit, budget, tier)."""
    db_client = DynamoDBClient()
    api_key_manager = APIKeyManager(db_client)
    result = api_key_manager.list_all_api_keys(limit=1000)
    config = {}
    for item in result.get("items", []):
        config[item.get("api_key")] = {
            "owner": item.get("owner_name") or item.get("user_id"),
            "user_id": item.get("user_id"),
            "daily_token_limit": float(item.get("daily_token_limit", 0) or 0),
            "daily_tokens_used": int(item.get("daily_tokens_used", 0) or 0),
            "monthly_budget": float(item.get("monthly_budget", 0) or 0),
            "budget_used_mtd": float(item.get("budget_used_mtd", 0) or 0),
            "service_tier": item.get("service_tier") or "default",
        }
    return config


@router.get("")
async def get_usage_stats(
    group: str = Query(default="range", pattern="^(range|day)$"),
    start: Optional[str] = Query(default=None, description="Local start datetime (to the minute)"),
    end: Optional[str] = Query(default=None, description="Local end datetime (to the minute)"),
    day: Optional[str] = Query(default=None, description="Local day YYYY-MM-DD (group=day)"),
    tz: Optional[str] = Query(default=None, description="IANA timezone for interpretation/display"),
    include_empty: bool = Query(default=False, description="Include users with no usage in range"),
):
    """Aggregate per-user usage over a time range or a single local day."""
    _require_mysql()
    tz_name = tz or settings.app_timezone

    # Resolve [start_utc, end_utc)
    if group == "day":
        if day:
            local_day = date.fromisoformat(day)
        else:
            from app.core.timezone import current_local_date

            local_day = current_local_date(tz_name)
        start_utc, end_utc = day_bounds_utc(local_day, tz_name)
        window = {"mode": "day", "day": local_day.isoformat(), "tz": tz_name}
    else:
        if not start or not end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start and end are required when group=range",
            )
        start_utc = parse_local_to_utc(start, tz_name)
        end_utc = parse_local_to_utc(end, tz_name)
        window = {"mode": "range", "start": start, "end": end, "tz": tz_name}

    from app.db.mysql.repositories import UsageDetailRepository

    aggregates = UsageDetailRepository.aggregate_by_key(start_utc, end_utc)
    agg_map = {a["api_key"]: a for a in aggregates}
    config = _key_config_map()

    rows = []
    keys = set(agg_map.keys())
    if include_empty:
        keys |= set(config.keys())

    for api_key in keys:
        cfg = config.get(api_key, {})
        agg = agg_map.get(api_key, {})
        rows.append(
            {
                "api_key": api_key,
                "owner": cfg.get("owner") or api_key,
                "user_id": cfg.get("user_id"),
                # Aggregated metrics (summed over the window)
                "input_tokens": int(agg.get("input_tokens", 0) or 0),
                "output_tokens": int(agg.get("output_tokens", 0) or 0),
                "cache_read_tokens": int(agg.get("cache_read_tokens", 0) or 0),
                "cache_write_tokens": int(agg.get("cache_write_tokens", 0) or 0),
                "total_tokens": int(agg.get("total_tokens", 0) or 0),
                "requests": int(agg.get("requests", 0) or 0),
                "total_cost": float(agg.get("total_cost", 0) or 0),
                # Per-user configuration attributes (not summed)
                "daily_token_limit": cfg.get("daily_token_limit", 0),
                "monthly_budget": cfg.get("monthly_budget", 0),
                "service_tier": cfg.get("service_tier", "default"),
            }
        )

    rows.sort(key=lambda r: r["total_tokens"], reverse=True)
    return {"window": window, "items": rows, "count": len(rows)}


@router.get("/day-navigation")
async def day_navigation(
    day: str = Query(..., description="Local day YYYY-MM-DD"),
    direction: str = Query(..., pattern="^(prev|next)$"),
):
    """Return the previous/next local day for the day-stats navigation control."""
    current = date.fromisoformat(day)
    delta = timedelta(days=1 if direction == "next" else -1)
    return {"day": (current + delta).isoformat()}
