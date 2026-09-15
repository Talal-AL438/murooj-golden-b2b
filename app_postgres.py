"""PostgreSQL production entrypoint.

This module leaves the SQLite demo untouched. In PostgreSQL mode it installs the
DB compatibility connection before importing the Flask application, so existing
modules receive the PostgreSQL-backed connection callback.
"""
import os
import sqlite3

from database_adapter import connect_db, is_postgres

if not is_postgres():
    raise RuntimeError("app_postgres.py requires DB_ENGINE=postgres")

# app.py and its extension modules call sqlite3.connect through their existing
# db() callback. Replace that constructor only inside this production process.
_original_sqlite_connect = sqlite3.connect
sqlite3.connect = lambda *args, **kwargs: connect_db()

from app import app  # noqa: E402,F401
