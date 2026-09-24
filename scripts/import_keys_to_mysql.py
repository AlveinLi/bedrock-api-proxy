#!/usr/bin/env python3
"""One-time import of existing API keys from DynamoDB into MySQL.

Use this when upgrading an environment that already has API keys in DynamoDB
to the MySQL-backed version. After this runs, MySQL holds a row for every
existing key, so the "MySQL is the source of truth" write path stays consistent
(edits/`sync-to-dynamo` will line up instead of silently no-op'ing on keys that
were never in MySQL).

Direction: DynamoDB -> MySQL (the admin "Sync to DynamoDB" button is the
opposite direction and must NOT be used for the initial seed).

Safe to re-run: rows are upserted by api_key, so existing MySQL rows are
updated in place (created_at is preserved by the repository).

Usage:
    uv run scripts/import_keys_to_mysql.py            # import all keys
    uv run scripts/import_keys_to_mysql.py --dry-run  # report only, no writes
    uv run scripts/import_keys_to_mysql.py --create-tables  # ensure schema first

Requires MYSQL_ENABLED=True and MYSQL_* connection settings (or MYSQL_DSN).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.dynamodb import APIKeyManager, DynamoDBClient  # noqa: E402
from app.db.mysql import is_enabled as mysql_enabled  # noqa: E402


def _iter_all_dynamo_keys(api_key_manager: APIKeyManager):
    """Yield every API key item from DynamoDB, following scan pagination."""
    last_key = None
    while True:
        result = api_key_manager.list_all_api_keys(limit=100, last_key=last_key)
        for item in result.get("items", []):
            yield item
        last_key = result.get("last_key")
        if not last_key:
            break


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import existing API keys from DynamoDB into MySQL (one-time seed)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report what would be imported without writing to MySQL.",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Ensure MySQL tables exist (runs init_db) before importing.",
    )
    args = parser.parse_args()

    if not mysql_enabled():
        print(
            "MYSQL_ENABLED is False. Set MYSQL_ENABLED=True (and MYSQL_* connection "
            "settings) before running this script."
        )
        return 1

    if args.create_tables and not args.dry_run:
        from app.db.mysql import init_db

        print("Ensuring MySQL tables exist...")
        init_db()

    # Imported lazily so --dry-run can still introspect without a live MySQL.
    from app.db.mysql.repositories import ApiKeyRepository
    from admin_portal.backend.services.api_key_store import _record_to_mysql

    print("Scanning DynamoDB API keys...")
    api_key_manager = APIKeyManager(DynamoDBClient())

    total = 0
    imported = 0
    failed = 0
    for item in _iter_all_dynamo_keys(api_key_manager):
        total += 1
        api_key = item.get("api_key")
        if not api_key:
            print("  ! skipping item without api_key")
            failed += 1
            continue

        masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else api_key
        if args.dry_run:
            print(f"  [dry-run] would import {masked} (user={item.get('user_id')})")
            imported += 1
            continue

        try:
            ApiKeyRepository.upsert(_record_to_mysql(item))
            imported += 1
            print(f"  imported {masked} (user={item.get('user_id')})")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failed += 1
            print(f"  ! failed {masked}: {exc}")

    print(f"\n{'=' * 50}")
    print("DynamoDB -> MySQL import complete" + (" (dry-run)" if args.dry_run else ""))
    print(f"  scanned:  {total}")
    print(f"  imported: {imported}")
    print(f"  failed:   {failed}")
    print(f"{'=' * 50}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
