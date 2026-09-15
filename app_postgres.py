"""PostgreSQL production entrypoint.

Keeps the SQLite demo untouched while bootstrapping the production PostgreSQL
schema before the existing Flask application and extensions are imported.
"""
import sqlite3

from database_adapter import connect_db, ensure_postgres_schema, is_postgres

if not is_postgres():
    raise RuntimeError("app_postgres.py requires DB_ENGINE=postgres")

# Create the PostgreSQL-native schema first. This avoids sending app.py's
# SQLite-only AUTOINCREMENT DDL to PostgreSQL on first request.
ensure_postgres_schema()

# Existing application modules receive their DB connection through sqlite3.connect.
# In this isolated production process only, route those calls to the compatibility
# adapter. The main/demo branch and its SQLite database remain unchanged.
sqlite3.connect = lambda *args, **kwargs: connect_db()

from app import app  # noqa: E402,F401
