"""
Public API — the single function users call to mount the panel.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sqlite_webpanel.db import Database
from sqlite_webpanel.router import build_router
import inspect

_STATIC_DIR = Path(__file__).parent / "static"


def mount_sqlite_panel(
    app: FastAPI,
    *,
    db_path: str | Path = "app.db",
    
    prefix: str = "/admin",
    read_only: bool = False,
    title: str = "SQLite Panel",
) -> None:
    """
    Mount a beautiful SQLite admin panel onto a FastAPI application.

    Parameters
    ----------
    app:
        Your FastAPI application instance.
    db_path:
        Path to the SQLite database file.  Created if it does not exist.
    prefix:
        URL prefix where the panel is mounted.  Default: ``/admin``.
    read_only:
        If ``True`` all write operations (insert/update/delete) are disabled.
    title:
        Display title shown in the panel header.
    """
    caller_dir = Path(inspect.stack()[1].filename).parent
    db_path = Path(db_path).resolve()
    db = Database(db_path)

    router = build_router(
        db=db,
        prefix=prefix,
        read_only=read_only,
        title=title,
    )

    # Serve static assets
    app.mount(
        f"{prefix}/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="sqlite_panel_static",
    )

    app.include_router(router, prefix=prefix)

def run_panel(
    db_path: str | Path = "app.db",
    *,
    host: str = "127.0.0.1",
    port: int = 8888,
    read_only: bool = False,
    title: str = "SQLite Panel",
    open_browser: bool = True,
):
    """
    Zero-config entry point. Creates its own FastAPI app + uvicorn server.
    Users just call this — no FastAPI or uvicorn knowledge needed.
    """
    import threading
    import webbrowser
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI()
    mount_sqlite_panel(app, db_path=db_path, prefix="/admin",
                       read_only=read_only, title=title)

    @app.get("/")
    def _root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/admin")

    if open_browser:
        def _open():
            import time; time.sleep(1.2)
            webbrowser.open(f"http://{host}:{port}/admin")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=host, port=port)
