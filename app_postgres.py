"""PostgreSQL production entrypoint.

Keeps the SQLite demo untouched while bootstrapping the production PostgreSQL
schema before the existing Flask application and extensions are imported.
"""
import sqlite3

from database_adapter import connect_db, ensure_postgres_schema, is_postgres

if not is_postgres():
    raise RuntimeError("app_postgres.py requires DB_ENGINE=postgres")

# Create the PostgreSQL-native schema before importing the existing Flask app.
ensure_postgres_schema()

# Route the existing app's sqlite3.connect calls through the PostgreSQL adapter
# only inside this isolated production process. The demo branch remains SQLite.
sqlite3.connect = lambda *args, **kwargs: connect_db()

from app import app  # noqa: E402


@app.get("/health/postgres")
def postgres_health():
    """Production readiness check without exposing credentials or business data."""
    conn = None
    try:
        conn = connect_db()
        row = conn.execute("SELECT 1 AS ok").fetchone()
        if not row or int(row["ok"]) != 1:
            raise RuntimeError("database readiness query failed")
        return {"ok": True, "database": "postgresql"}, 200
    except Exception:
        app.logger.exception("PostgreSQL readiness check failed")
        return {"ok": False, "database": "postgresql"}, 503
    finally:
        if conn is not None:
            conn.close()
