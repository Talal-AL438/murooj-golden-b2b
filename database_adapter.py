import os
import re
import sqlite3
from contextlib import closing

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # SQLite demo can still run without PostgreSQL driver
    psycopg2 = None
    RealDictCursor = None


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(APP_DIR, "murooj.db")
SERIAL_ID_TABLES = {
    "users", "agencies", "hotels", "hotel_images", "requests", "offers",
    "notifications", "audit", "login_attempts", "trusted_admin_devices",
    "pending_admin_devices",
}

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'agency',name TEXT,job_title TEXT,mobile TEXT,language TEXT DEFAULT 'ar',active INTEGER DEFAULT 1,created_at TEXT NOT NULL,department TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS agencies (id BIGSERIAL PRIMARY KEY,user_id BIGINT UNIQUE NOT NULL REFERENCES users(id),agency_name TEXT NOT NULL,country TEXT NOT NULL,contact_name TEXT NOT NULL,whatsapp TEXT NOT NULL,category TEXT DEFAULT 'New',verified INTEGER DEFAULT 0,internal_notes TEXT DEFAULT '',marketing_consent INTEGER DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hotels (id BIGSERIAL PRIMARY KEY,name_ar TEXT NOT NULL,name_en TEXT NOT NULL,city TEXT NOT NULL,map_url TEXT,services TEXT,meals TEXT,active INTEGER DEFAULT 1,sort_order INTEGER DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hotel_images (id BIGSERIAL PRIMARY KEY,hotel_id BIGINT NOT NULL REFERENCES hotels(id),image_url TEXT NOT NULL,sort_order INTEGER DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requests (id BIGSERIAL PRIMARY KEY,agency_id BIGINT NOT NULL REFERENCES agencies(id),hotel_id BIGINT REFERENCES hotels(id),any_hotel INTEGER DEFAULT 0,city TEXT NOT NULL,checkin TEXT,checkout TEXT,rooms INTEGER,persons INTEGER,nationality TEXT,meal TEXT,notes TEXT,status TEXT DEFAULT 'sent',created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offers (id BIGSERIAL PRIMARY KEY,title TEXT NOT NULL,hotel_id BIGINT REFERENCES hotels(id),start_date TEXT,end_date TEXT,meal TEXT,note TEXT,audience TEXT DEFAULT 'all',language_mode TEXT DEFAULT 'auto',manual_language TEXT DEFAULT 'ar',active INTEGER DEFAULT 1,pinned INTEGER DEFAULT 0,sort_order INTEGER DEFAULT 0,created_at TEXT NOT NULL,image_url TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS offer_targets (offer_id BIGINT NOT NULL REFERENCES offers(id),agency_id BIGINT NOT NULL REFERENCES agencies(id),PRIMARY KEY(offer_id,agency_id));
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


def database_engine():
    return (os.environ.get("DB_ENGINE") or "sqlite").strip().lower()


def is_postgres():
    return database_engine() in {"postgres", "postgresql"}


def sqlite_path():
    return os.environ.get("DB_PATH") or DEFAULT_SQLITE_PATH


def _qmark_to_percent(sql_text):
    return sql_text.replace("?", "%s")


def _translate_postgres_sql(sql_text):
    stripped = sql_text.strip()
    low = stripped.lower()
    if "from sqlite_master" in low:
        return "SELECT table_name AS name FROM information_schema.tables WHERE table_schema='public'"
    pragma = re.match(r"pragma\s+table_info\(([^)]+)\)", stripped, flags=re.I)
    if pragma:
        table = pragma.group(1).strip().strip("'\"")
        return (
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position"
        ), (table,)
    return _qmark_to_percent(sql_text)


class CursorProxy:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class PostgresConnectionProxy:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, statement, params=()):
        translated = _translate_postgres_sql(statement)
        if isinstance(translated, tuple):
            statement, forced_params = translated
            params = forced_params
        else:
            statement = translated

        stripped = statement.strip()
        insert_match = re.match(r"insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)", stripped, flags=re.I)
        insert_ignore = re.match(r"insert\s+or\s+ignore\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)", stripped, flags=re.I)
        if insert_ignore:
            table = insert_ignore.group(1)
            statement = re.sub(r"^\s*insert\s+or\s+ignore\s+into", "INSERT INTO", statement, count=1, flags=re.I)
            if " on conflict " not in statement.lower():
                statement = statement.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
            insert_match = re.match(r"insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)", statement.strip(), flags=re.I)

        cur = self._raw.cursor(cursor_factory=RealDictCursor)
        lastrowid = None
        table = insert_match.group(1).lower() if insert_match else None
        if table in SERIAL_ID_TABLES and " returning " not in statement.lower() and " on conflict " not in statement.lower():
            statement = statement.rstrip().rstrip(";") + " RETURNING id"
            cur.execute(statement, tuple(params or ()))
            row = cur.fetchone()
            if row:
                lastrowid = row.get("id")
        else:
            cur.execute(statement, tuple(params or ()))
        return CursorProxy(cur, lastrowid=lastrowid)

    def executescript(self, script):
        cur = self._raw.cursor()
        cur.execute(script)
        return CursorProxy(cur)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()



def connect_db():
    if is_postgres():
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for PostgreSQL mode")
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise RuntimeError("DATABASE_URL is required when DB_ENGINE=postgres")
        return PostgresConnectionProxy(psycopg2.connect(url))
    conn = sqlite3.connect(sqlite_path())
    conn.row_factory = sqlite3.Row
    return conn


def ensure_postgres_schema(conn=None):
    if not is_postgres():
        return
    owned = conn is None
    c = conn or connect_db()
    try:
        c.executescript(POSTGRES_SCHEMA)
        c.commit()
    finally:
        if owned:
            c.close()


def backend_name():
    return "postgresql" if is_postgres() else "sqlite"
