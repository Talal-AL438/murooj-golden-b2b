"""PostgreSQL production entrypoint.

Keeps the SQLite demo untouched while bootstrapping the production PostgreSQL
schema before the existing Flask application and extensions are imported.
"""
import sqlite3

from database_adapter import connect_db, ensure_postgres_schema, is_postgres

if not is_postgres():
    raise RuntimeError("app_postgres.py requires DB_ENGINE=postgres")

ensure_postgres_schema()
sqlite3.connect = lambda *args, **kwargs: connect_db()

from app import app  # noqa: E402
from password_recovery import register_password_recovery  # noqa: E402

register_password_recovery(app)


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


@app.get("/health/postgres/schema")
def postgres_schema_health():
    """Read-only smoke test for the production tables used by core portal flows."""
    conn = None
    required = (
        "settings", "users", "agencies", "hotels", "hotel_images", "requests",
        "offers", "offer_targets", "notifications", "audit", "staff_permissions",
        "login_attempts", "trusted_admin_devices", "pending_admin_devices",
    )
    try:
        conn = connect_db()
        counts = {}
        for table in required:
            row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            counts[table] = int(row["count"])
        return {"ok": True, "database": "postgresql", "tables": len(counts)}, 200
    except Exception:
        app.logger.exception("PostgreSQL schema smoke test failed")
        return {"ok": False, "database": "postgresql"}, 503
    finally:
        if conn is not None:
            conn.close()
