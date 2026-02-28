"""
sqlite_webpanel: A plug-and-play SQLite admin panel for FastAPI.

Usage:
    from sqlite_webpanel import mount_sqlite_panel, Database, _safe_identifier

    mount_sqlite_panel(app, db_path="app.db")
"""

from .mount import mount_sqlite_panel, run_panel
from .db import Database, _safe_identifier
from .renderers import render_cell

__all__ = [
    "mount_sqlite_panel",
    "Database",
    "_safe_identifier",
    "render_cell",
    "run_panel"
    # add other things you want exposed
]

__version__ = "0.1.0"