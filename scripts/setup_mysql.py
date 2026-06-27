"""Create MySQL tables for the proxy persistence layer.

Usage:
    uv run scripts/setup_mysql.py

Requires MYSQL_* env vars (or MYSQL_DSN) and MYSQL_ENABLED=True.
Creates: <prefix>api_keys, <prefix>usage_detail, <prefix>content_audit,
<prefix>content_audit_archive_history.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings  # noqa: E402
from app.db.mysql import init_db, is_enabled  # noqa: E402


def main() -> int:
    if not is_enabled():
        print(
            "MYSQL_ENABLED is False. Set MYSQL_ENABLED=True (and MYSQL_* connection "
            "settings) before running this script."
        )
        return 1

    print(
        f"Connecting to MySQL host={settings.mysql_host} port={settings.mysql_port} "
        f"db={settings.mysql_database} prefix={settings.mysql_table_prefix!r}"
    )
    init_db()
    print("MySQL tables created/ensured successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
