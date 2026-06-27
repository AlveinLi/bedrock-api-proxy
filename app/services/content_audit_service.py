"""Content audit service.

Persists the full content of each request (prompt: system + messages + tools)
and the corresponding LLM response to MySQL, for auditing purposes.

This is INTENTIONALLY independent of ``OTEL_TRACE_CONTENT``: content auditing is
always performed when ``CONTENT_AUDIT_ENABLED`` is true, regardless of the OTEL
setting (OTEL only affects observability output, not auditing).

Writes are performed asynchronously on a background worker thread so the request
hot path is never blocked. If the queue is full or MySQL is unavailable, audit
records are dropped with a log entry rather than impacting the request.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.timezone import now_utc

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
    except Exception:  # pragma: no cover
        pass
    return str(obj)


def _to_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=_json_default, ensure_ascii=False)
    except (TypeError, ValueError):  # pragma: no cover
        return str(value)


def _dump_messages(messages: Any) -> Optional[str]:
    """Serialize request messages (list of pydantic models or dicts)."""
    if messages is None:
        return None
    out: List[Any] = []
    for m in messages:
        if hasattr(m, "model_dump"):
            out.append(m.model_dump())
        else:
            out.append(m)
    return _to_json(out)


class ContentAuditService:
    """Background worker that writes content audit records to MySQL."""

    def __init__(self, max_size: int = 10000):
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=max_size)
        self._worker: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._dropped = 0

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker = threading.Thread(
                target=self._run, name="content-audit-worker", daemon=True
            )
            self._worker.start()
            logger.info("ContentAuditService worker started")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        # Wake the worker with a sentinel
        try:
            self._queue.put_nowait({"__stop__": True})
        except queue.Full:  # pragma: no cover
            pass

    def _run(self) -> None:
        from app.db.mysql.repositories import ContentAuditRepository

        while self._running:
            try:
                record = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            if record.get("__stop__"):
                break
            try:
                ContentAuditRepository.insert(record)
            except Exception as exc:  # pragma: no cover - never crash the worker
                logger.error("Failed to persist content audit record: %s", exc)
            finally:
                self._queue.task_done()

    def enqueue(self, record: Dict[str, Any]) -> None:
        if not self._running:
            self.start()
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            self._dropped += 1
            if self._dropped % 100 == 1:
                logger.warning(
                    "Content audit queue full; dropped %d records so far", self._dropped
                )


_service: Optional[ContentAuditService] = None
_service_lock = threading.Lock()


def get_content_audit_service() -> ContentAuditService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = ContentAuditService(
                    max_size=settings.content_audit_queue_max_size
                )
    return _service


def start_content_audit() -> None:
    if settings.content_audit_enabled:
        get_content_audit_service().start()


def stop_content_audit() -> None:
    if _service is not None:
        _service.stop()


def record_content_audit(
    *,
    request_id: Optional[str],
    api_key: Optional[str],
    user_id: Optional[str] = None,
    owner_name: Optional[str] = None,
    request_time: Optional[datetime] = None,
    model: Optional[str] = None,
    resolved_model: Optional[str] = None,
    api_surface: Optional[str] = None,
    service_tier: Optional[str] = None,
    system_prompt: Any = None,
    request_messages: Any = None,
    tools: Any = None,
    response_content: Optional[str] = None,
    stop_reason: Optional[str] = None,
    streaming: bool = False,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    reasoning_tokens: int = 0,
    total_tokens: Optional[int] = None,
    cost: float = 0.0,
    duration_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> None:
    """Build and enqueue a content audit record (no-op if disabled/MySQL off)."""
    if not settings.content_audit_enabled:
        return
    try:
        from app.db.mysql import is_enabled as mysql_enabled

        if not mysql_enabled():
            return
    except Exception:  # pragma: no cover
        return

    if total_tokens is None:
        total_tokens = (
            int(input_tokens)
            + int(output_tokens)
            + int(cache_read_tokens)
            + int(cache_write_tokens)
        )

    record = {
        "request_id": request_id,
        "api_key": api_key or "",
        "user_id": user_id,
        "owner_name": owner_name,
        "request_time": request_time or now_utc(),
        "model": model,
        "resolved_model": resolved_model,
        "api_surface": api_surface,
        "service_tier": service_tier,
        "system_prompt": _to_json(system_prompt),
        "request_messages": _dump_messages(request_messages),
        "tools": _to_json(tools),
        "response_content": response_content,
        "stop_reason": stop_reason,
        "streaming": bool(streaming),
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "cache_read_tokens": int(cache_read_tokens or 0),
        "cache_write_tokens": int(cache_write_tokens or 0),
        "reasoning_tokens": int(reasoning_tokens or 0),
        "total_tokens": int(total_tokens or 0),
        "cost": float(cost or 0.0),
        "duration_ms": duration_ms,
        "success": bool(success),
        "error_message": error_message,
        "client_ip": client_ip,
        "created_at": now_utc(),
    }
    get_content_audit_service().enqueue(record)
