"""Safe production PostgreSQL preflight.

Run with DB_ENGINE=postgres and DATABASE_URL configured. It verifies encrypted
connectivity, schema presence, and basic read/write behavior without touching
business records.
"""
import os
import secrets
from datetime import datetime

from database_adapter import backend_name, connect_db, ensure_postgres_schema


def main():
    if backend_name() != "postgresql":
        raise SystemExit("FAIL: DB_ENGINE must be postgres")
    if not os.environ.get("DATABASE_URL", "").strip():
        raise SystemExit("FAIL: DATABASE_URL is missing")

    ensure_postgres_schema()
    db = connect_db()
    marker = "preflight_" + secrets.token_hex(8)
    try:
        tables = db.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema='public'").fetchall()
        names = {r['name'] for r in tables}
        required = {
            'settings','users','agencies','hotels','hotel_images','requests','offers',
            'offer_targets','notifications','audit','staff_permissions','login_attempts',
            'trusted_admin_devices','pending_admin_devices'
        }
        missing = sorted(required - names)
        if missing:
            raise RuntimeError("Missing tables: " + ", ".join(missing))

        db.execute("INSERT INTO settings(key,value) VALUES(?,?)", (marker, datetime.utcnow().isoformat()))
        row = db.execute("SELECT value FROM settings WHERE key=?", (marker,)).fetchone()
        if not row or not row['value']:
            raise RuntimeError("Read/write verification failed")
        db.execute("DELETE FROM settings WHERE key=?", (marker,))
        db.commit()
        print("PASS: PostgreSQL connectivity, schema, and read/write checks succeeded")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
