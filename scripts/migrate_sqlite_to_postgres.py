"""One-time SQLite -> PostgreSQL migration utility for Murooj Golden B2B.

Usage at production cutover:
  SOURCE_SQLITE=/path/to/murooj.db DATABASE_URL=postgresql://... python scripts/migrate_sqlite_to_postgres.py

The script is intentionally not run automatically by the web app. It creates the
production schema, copies all current portal data in dependency order, and resets
PostgreSQL sequences. Run it only during a planned maintenance/cutover window
from a verified SQLite backup.
"""

import os
import sqlite3
import sys
from contextlib import closing
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg2
from psycopg2 import sql

SOURCE_SQLITE = os.environ.get("SOURCE_SQLITE", "murooj.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'agency',name TEXT,job_title TEXT,mobile TEXT,language TEXT DEFAULT 'ar',active INTEGER DEFAULT 1,created_at TEXT NOT NULL,department TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS agencies (id BIGSERIAL PRIMARY KEY,user_id BIGINT UNIQUE NOT NULL REFERENCES users(id),agency_name TEXT NOT NULL,country TEXT NOT NULL,contact_name TEXT NOT NULL,whatsapp TEXT NOT NULL,category TEXT DEFAULT 'New',verified INTEGER DEFAULT 0,internal_notes TEXT DEFAULT '',marketing_consent INTEGER DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hotels (id BIGSERIAL PRIMARY KEY,name_ar TEXT NOT NULL,name_en TEXT NOT NULL,city TEXT NOT NULL,map_url TEXT,services TEXT,meals TEXT,active INTEGER DEFAULT 1,sort_order INTEGER DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hotel_images (id BIGSERIAL PRIMARY KEY,hotel_id BIGINT NOT NULL REFERENCES hotels(id),image_url TEXT NOT NULL,sort_order INTEGER DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requests (id BIGSERIAL PRIMARY KEY,agency_id BIGINT NOT NULL REFERENCES agencies(id),hotel_id BIGINT REFERENCES hotels(id),any_hotel INTEGER DEFAULT 0,city TEXT NOT NULL,checkin TEXT,checkout TEXT,rooms INTEGER,persons INTEGER,nationality TEXT,meal TEXT,notes TEXT,status TEXT DEFAULT 'sent',created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offers (id BIGSERIAL PRIMARY KEY,title TEXT NOT NULL,hotel_id BIGINT REFERENCES hotels(id),start_date TEXT,end_date TEXT,meal TEXT,note TEXT,audience TEXT DEFAULT 'all',language_mode TEXT DEFAULT 'auto',manual_language TEXT DEFAULT 'ar',active INTEGER DEFAULT 1,pinned INTEGER DEFAULT 0,sort_order INTEGER DEFAULT 0,created_at TEXT NOT NULL,image_url TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS offer_targets (offer_id BIGINT NOT NULL REFERENCES offers(id),agency_id BIGINT NOT NULL REFERENCES agencies(id),PRIMARY KEY (offer_id,agency_id));
CREATE TABLE IF NOT EXISTS notifications (id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id),type TEXT NOT NULL,ref_id BIGINT,title TEXT NOT NULL,body TEXT,link TEXT,read_at TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id),action TEXT NOT NULL,details TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS staff_permissions (user_id BIGINT PRIMARY KEY REFERENCES users(id),reports INTEGER DEFAULT 0,agencies INTEGER DEFAULT 0,hotels INTEGER DEFAULT 0,offers INTEGER DEFAULT 0,updated_at TEXT);
CREATE TABLE IF NOT EXISTS login_attempts (id BIGSERIAL PRIMARY KEY,email TEXT,ip TEXT,success INTEGER DEFAULT 0,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup ON login_attempts(email,ip,created_at);
CREATE TABLE IF NOT EXISTS trusted_admin_devices (id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id),token_hash TEXT NOT NULL UNIQUE,user_agent TEXT,created_at TEXT NOT NULL,last_seen_at TEXT,approved_by BIGINT,active INTEGER DEFAULT 1);
CREATE INDEX IF NOT EXISTS idx_trusted_admin_devices_user ON trusted_admin_devices(user_id,active);
CREATE TABLE IF NOT EXISTS pending_admin_devices (id BIGSERIAL PRIMARY KEY,user_id BIGINT NOT NULL REFERENCES users(id),token_hash TEXT NOT NULL,user_agent TEXT,ip TEXT,created_at TEXT NOT NULL,approved_at TEXT,approved_by BIGINT,rejected_at TEXT);
CREATE INDEX IF NOT EXISTS idx_pending_admin_devices_user ON pending_admin_devices(user_id,approved_at,rejected_at);
"""

COPY_ORDER = ["settings","users","agencies","hotels","hotel_images","requests","offers","offer_targets","notifications","audit","staff_permissions","login_attempts","trusted_admin_devices","pending_admin_devices"]


def secure_postgres_url(url):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["sslmode"] = os.environ.get("PGSSLMODE", "require")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def sqlite_tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def sqlite_columns(conn, table):
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def postgres_columns(cur, table):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
    return [row[0] for row in cur.fetchall()]


def copy_table(src, dst, table):
    if table not in sqlite_tables(src):
        print(f"skip {table}: not present in SQLite")
        return 0
    src_cols = sqlite_columns(src, table)
    dst_cols = postgres_columns(dst, table)
    cols = [c for c in src_cols if c in dst_cols]
    if not cols:
        print(f"skip {table}: no common columns")
        return 0
    rows = src.execute("SELECT " + ",".join('"' + c.replace('"','""') + '"' for c in cols) + f' FROM "{table}"').fetchall()
    if not rows:
        print(f"copy {table}: 0 rows")
        return 0
    insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(sql.Identifier(table),sql.SQL(", ").join(map(sql.Identifier,cols)),sql.SQL(", ").join(sql.Placeholder()*len(cols)))
    for row in rows:
        dst.execute(insert_stmt, tuple(row[c] for c in cols))
    print(f"copy {table}: {len(rows)} rows")
    return len(rows)


def reset_sequence(cur, table):
    columns = postgres_columns(cur, table)
    if "id" not in columns:
        return
    cur.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM {}), 1), COALESCE((SELECT MAX(id) FROM {}), 0) > 0)").format(sql.Identifier(table),sql.Identifier(table)),(table,))


def main():
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is required")
    if not os.path.exists(SOURCE_SQLITE):
        raise SystemExit(f"SQLite source not found: {SOURCE_SQLITE}")
    with closing(sqlite3.connect(SOURCE_SQLITE)) as src:
        src.row_factory = sqlite3.Row
        with closing(psycopg2.connect(secure_postgres_url(DATABASE_URL))) as pg:
            pg.autocommit = False
            try:
                with pg.cursor() as cur:
                    cur.execute(SCHEMA_SQL)
                    for table in COPY_ORDER:
                        copy_table(src,cur,table)
                    for table in COPY_ORDER:
                        if table not in ("settings","offer_targets","staff_permissions"):
                            reset_sequence(cur,table)
                pg.commit()
            except Exception:
                pg.rollback()
                raise
    print("Migration completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        raise
