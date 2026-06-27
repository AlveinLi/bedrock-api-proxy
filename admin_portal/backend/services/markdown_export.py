"""Markdown export helpers for content audit records."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.timezone import to_tz


def _fmt_time(value: Any, tz_name: Optional[str]) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return to_tz(value, tz_name).strftime("%Y-%m-%d %H:%M:%S %Z")
    return str(value)


def _pretty_json(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            return value
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def record_to_markdown(record: Dict[str, Any], tz_name: Optional[str] = None) -> str:
    """Render a single content audit record as a markdown section."""
    lines: List[str] = []
    lines.append(f"## Request `{record.get('request_id') or record.get('id')}`")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Owner | {record.get('owner_name') or ''} |")
    lines.append(f"| User ID | {record.get('user_id') or ''} |")
    lines.append(f"| Request time | {_fmt_time(record.get('request_time'), tz_name)} |")
    lines.append(f"| Model | {record.get('model') or ''} |")
    lines.append(f"| Resolved model | {record.get('resolved_model') or ''} |")
    lines.append(f"| API surface | {record.get('api_surface') or ''} |")
    lines.append(f"| Service tier | {record.get('service_tier') or ''} |")
    lines.append(f"| Streaming | {record.get('streaming')} |")
    lines.append(f"| Stop reason | {record.get('stop_reason') or ''} |")
    lines.append(
        f"| Tokens (in/out/cr/cw) | "
        f"{record.get('input_tokens', 0)}/{record.get('output_tokens', 0)}/"
        f"{record.get('cache_read_tokens', 0)}/{record.get('cache_write_tokens', 0)} |"
    )
    lines.append(f"| Total tokens | {record.get('total_tokens', 0)} |")
    lines.append(f"| Cost | {record.get('cost', 0)} |")
    lines.append(f"| Duration (ms) | {record.get('duration_ms') or ''} |")
    lines.append(f"| Success | {record.get('success')} |")
    if record.get("error_message"):
        lines.append(f"| Error | {record.get('error_message')} |")
    lines.append("")

    system_prompt = record.get("system_prompt")
    if system_prompt:
        lines.append("### System")
        lines.append("")
        lines.append("```json")
        lines.append(_pretty_json(system_prompt))
        lines.append("```")
        lines.append("")

    tools = record.get("tools")
    if tools:
        lines.append("### Tools")
        lines.append("")
        lines.append("```json")
        lines.append(_pretty_json(tools))
        lines.append("```")
        lines.append("")

    lines.append("### Request messages")
    lines.append("")
    lines.append("```json")
    lines.append(_pretty_json(record.get("request_messages")))
    lines.append("```")
    lines.append("")

    lines.append("### Response")
    lines.append("")
    lines.append(record.get("response_content") or "_(empty)_")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def records_to_markdown(
    records: List[Dict[str, Any]],
    tz_name: Optional[str] = None,
    title: str = "Content Audit Export",
) -> str:
    """Render a list of records into a full markdown document."""
    header = [f"# {title}", "", f"Total records: {len(records)}", "", ""]
    body = [record_to_markdown(r, tz_name) for r in records]
    return "\n".join(header) + "\n".join(body)
