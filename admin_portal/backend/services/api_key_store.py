"""API key master store.

Implements the "MySQL is the source of truth, DynamoDB is the runtime store"
model:

- On create/update/delete, the change is written to MySQL first, then synced to
  DynamoDB (which the proxy reads at request time).
- ``sync_all_to_dynamo`` overwrites DynamoDB from the full MySQL set (used for
  system initialization or to force DynamoDB back in line with MySQL).

When MySQL is disabled (``MYSQL_ENABLED=False``), all operations fall back to
DynamoDB-only so the admin portal keeps working without MySQL.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings
from app.db.dynamodb import APIKeyManager
from app.db.mysql import is_enabled as mysql_enabled

logger = logging.getLogger(__name__)


def _epoch_to_dt(value: Any) -> datetime:
    """Convert an int epoch (or datetime/None) to a UTC datetime."""
    if isinstance(value, datetime):
        return value
    if value is None:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, OSError, OverflowError, TypeError):
        return datetime.now(timezone.utc)


def _dt_to_epoch(value: Any) -> int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    try:
        return int(value)
    except (ValueError, TypeError):
        return int(time.time())


def _record_to_mysql(record: Dict[str, Any]) -> Dict[str, Any]:
    """Map a canonical record into MySQL ApiKeyRecord columns."""
    metadata = record.get("metadata")
    if isinstance(metadata, (dict, list)):
        metadata_json = json.dumps(metadata)
    else:
        metadata_json = metadata if isinstance(metadata, str) else None

    return {
        "api_key": record.get("api_key"),
        "user_id": record.get("user_id"),
        "name": record.get("name"),
        "owner_name": record.get("owner_name"),
        "role": record.get("role"),
        "is_active": bool(record.get("is_active", True)),
        "rate_limit": record.get("rate_limit"),
        "tpm_limit": record.get("tpm_limit"),
        "service_tier": record.get("service_tier"),
        "monthly_budget": float(record.get("monthly_budget", 0) or 0),
        "budget_used": float(record.get("budget_used", 0) or 0),
        "budget_used_mtd": float(record.get("budget_used_mtd", 0) or 0),
        "budget_mtd_month": record.get("budget_mtd_month"),
        "budget_history": record.get("budget_history"),
        "daily_token_limit": float(record.get("daily_token_limit", 0) or 0),
        "daily_tokens_used": int(record.get("daily_tokens_used", 0) or 0),
        "daily_tokens_date": record.get("daily_tokens_date"),
        "deactivated_reason": record.get("deactivated_reason"),
        "cache_ttl": record.get("cache_ttl"),
        "routing_strategy": record.get("routing_strategy"),
        "compression_strategy": record.get("compression_strategy"),
        "provider_id": record.get("provider_id"),
        "metadata_json": metadata_json,
        "created_at": _epoch_to_dt(record.get("created_at")),
        "updated_at": _epoch_to_dt(record.get("updated_at") or record.get("created_at")),
    }


def _mysql_to_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a MySQL ApiKeyRecord row into a canonical DynamoDB-friendly record."""
    metadata_json = row.get("metadata_json")
    metadata: Any = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    return {
        "api_key": row.get("api_key"),
        "user_id": row.get("user_id"),
        "name": row.get("name"),
        "owner_name": row.get("owner_name"),
        "role": row.get("role"),
        "is_active": bool(row.get("is_active", True)),
        "rate_limit": row.get("rate_limit"),
        "tpm_limit": row.get("tpm_limit"),
        "service_tier": row.get("service_tier"),
        "monthly_budget": float(row.get("monthly_budget", 0) or 0),
        "budget_used": float(row.get("budget_used", 0) or 0),
        "budget_used_mtd": float(row.get("budget_used_mtd", 0) or 0),
        "budget_mtd_month": row.get("budget_mtd_month"),
        "budget_history": row.get("budget_history") or "{}",
        "daily_token_limit": float(row.get("daily_token_limit", 0) or 0),
        "daily_tokens_used": int(row.get("daily_tokens_used", 0) or 0),
        "daily_tokens_date": row.get("daily_tokens_date"),
        "deactivated_reason": row.get("deactivated_reason"),
        "cache_ttl": row.get("cache_ttl"),
        "routing_strategy": row.get("routing_strategy") or "off",
        "compression_strategy": row.get("compression_strategy") or "off",
        "provider_id": row.get("provider_id"),
        "metadata": metadata,
        "created_at": _dt_to_epoch(row.get("created_at")),
        "updated_at": _dt_to_epoch(row.get("updated_at")),
    }


def _write_mysql(record: Dict[str, Any]) -> None:
    if not mysql_enabled():
        return
    try:
        from app.db.mysql.repositories import ApiKeyRepository

        ApiKeyRepository.upsert(_record_to_mysql(record))
    except Exception as exc:  # pragma: no cover - never break the admin op
        logger.error("Failed to write API key to MySQL: %s", exc)


def create_api_key(
    api_key_manager: APIKeyManager,
    *,
    user_id: str,
    name: str,
    owner_name: Optional[str] = None,
    role: Optional[str] = None,
    monthly_budget: Optional[float] = None,
    daily_token_limit: Optional[float] = None,
    rate_limit: Optional[int] = None,
    service_tier: Optional[str] = None,
    cache_ttl: Optional[str] = None,
    routing_strategy: Optional[str] = None,
    compression_strategy: Optional[str] = None,
    provider_id: Optional[str] = None,
) -> str:
    """Create an API key: build canonical record, write MySQL, then DynamoDB."""
    from app.core.timezone import current_day_key

    api_key = f"sk-{uuid4().hex}"
    now = int(time.time())
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")

    record = {
        "api_key": api_key,
        "user_id": user_id,
        "name": name,
        "owner_name": owner_name or user_id,
        "role": role or "Full Access",
        "is_active": True,
        "rate_limit": rate_limit or settings.rate_limit_requests,
        "tpm_limit": 100000,
        "service_tier": service_tier or settings.default_service_tier,
        "monthly_budget": float(monthly_budget or 0),
        "budget_used": 0.0,
        "budget_used_mtd": 0.0,
        "budget_mtd_month": current_month,
        "budget_history": "{}",
        "daily_token_limit": float(daily_token_limit or 0),
        "daily_tokens_used": 0,
        "daily_tokens_date": current_day_key(),
        "deactivated_reason": None,
        "cache_ttl": cache_ttl,
        "routing_strategy": routing_strategy or "off",
        "compression_strategy": compression_strategy or "off",
        "provider_id": provider_id,
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }

    # MySQL first (source of truth), then DynamoDB (runtime store).
    _write_mysql(record)
    api_key_manager.upsert_from_record(record)
    return api_key


def update_api_key(
    api_key_manager: APIKeyManager,
    api_key: str,
    update_data: Dict[str, Any],
) -> bool:
    """Update an API key in MySQL first, then DynamoDB."""
    # MySQL first
    if mysql_enabled() and update_data:
        try:
            from app.db.mysql.repositories import ApiKeyRepository

            mysql_fields = dict(update_data)
            # cache_ttl "none" sentinel clears the value
            if mysql_fields.get("cache_ttl") == "none":
                mysql_fields["cache_ttl"] = None
            ApiKeyRepository.set_fields(api_key, **mysql_fields)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to update API key in MySQL: %s", exc)

    # Then DynamoDB
    return api_key_manager.update_api_key(api_key, **update_data)


def delete_api_key(api_key_manager: APIKeyManager, api_key: str) -> bool:
    """Delete an API key from MySQL first, then DynamoDB."""
    if mysql_enabled():
        try:
            from app.db.mysql.repositories import ApiKeyRepository

            ApiKeyRepository.delete(api_key)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to delete API key in MySQL: %s", exc)
    return api_key_manager.delete_api_key(api_key)


def set_active(
    api_key_manager: APIKeyManager,
    api_key: str,
    is_active: bool,
    reason: Optional[str] = None,
) -> bool:
    """Set active state in MySQL first, then DynamoDB."""
    fields: Dict[str, Any] = {"is_active": is_active}
    if is_active:
        fields["deactivated_reason"] = None
    elif reason:
        fields["deactivated_reason"] = reason
    if mysql_enabled():
        try:
            from app.db.mysql.repositories import ApiKeyRepository

            ApiKeyRepository.set_fields(api_key, **fields)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to set active state in MySQL: %s", exc)
    if is_active:
        return api_key_manager.reactivate_api_key(api_key)
    return api_key_manager.deactivate_api_key(api_key, reason=reason) or True


def sync_all_to_dynamo(api_key_manager: APIKeyManager) -> Dict[str, Any]:
    """Overwrite DynamoDB with every API key record from MySQL.

    Used for system initialization or to force DynamoDB back in line with the
    MySQL master store.
    """
    if not mysql_enabled():
        return {"synced": 0, "failed": 0, "error": "MySQL is not enabled"}

    from app.db.mysql.repositories import ApiKeyRepository

    rows = ApiKeyRepository.list_all()
    synced = 0
    failed = 0
    for row in rows:
        record = _mysql_to_record(row)
        if api_key_manager.upsert_from_record(record):
            synced += 1
        else:
            failed += 1
    return {"synced": synced, "failed": failed, "total": len(rows)}


def list_all_records() -> List[Dict[str, Any]]:
    """Return all API key records from MySQL as canonical records."""
    if not mysql_enabled():
        return []
    from app.db.mysql.repositories import ApiKeyRepository

    return [_mysql_to_record(r) for r in ApiKeyRepository.list_all()]
