"""Read-only verification after SQLite -> PostgreSQL migration.

Usage:
  SOURCE_SQLITE=/path/to/murooj.db DATABASE_URL=postgresql://... python scripts/verify_postgres_migration.py

Exit code 0 means table row counts match for every table that exists in the
SQLite source. This is intended to be run before production traffic is enabled.
"""

import os
import sqlite3
import sys
from contextlib import closing

import psycopg2
from psycopg2 import sql

SOURCE_SQLITE = os.environ.get("SOURCE_SQLITE", "murooj.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
TABLES = [
    "settings", "users", "agencies", "hotels", "hotel_images", "requests",
    "offers", "offer_targets", "notifications", "audit", "staff_permissions",
    "login_attempts", "trusted_admin_devices", "pending_admin_devices",
]


def main():
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is required")
    if not os.path.exists(SOURCE_SQLITE):
        raise SystemExit(f"SQLite source not found: {SOURCE_SQLITE}")

    failures = []
    with closing(sqlite3.connect(SOURCE_SQLITE)) as src, closing(psycopg2.connect(DATABASE_URL)) as pg:
        src_tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with pg.cursor() as cur:
            for table in TABLES:
                if table not in src_tables:
                    continue
                sqlite_count = src.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                postgres_count = cur.fetchone()[0]
                state = "OK" if sqlite_count == postgres_count else "MISMATCH"
                print(f"{state:8} {table:24} sqlite={sqlite_count} postgres={postgres_count}")
                if sqlite_count != postgres_count:
                    failures.append(table)

    if failures:
        print("Verification failed for: " + ", ".join(failures), file=sys.stderr)
        return 1
    print("All migrated table counts match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
