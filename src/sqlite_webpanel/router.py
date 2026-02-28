"""
Web layer — FastAPI router that exposes all panel endpoints.
Completely decoupled from the DB logic via sqlite_panel.db.Database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from sqlite_webpanel.db import Database
from sqlite_webpanel.renderers import render_cell

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _make_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    templates.env.globals["render_cell"] = render_cell
    templates.env.globals["enumerate"] = enumerate
    templates.env.globals["min"] = min
    templates.env.filters["tojson_pretty"] = lambda v: json.dumps(v, indent=2)
    return templates


def build_router(
    db: Database,
    prefix: str,
    read_only: bool,
    title: str,
) -> APIRouter:
    router = APIRouter()
    templates = _make_templates()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _get_db() -> Database:
        return db

    def _require_write() -> None:
        if read_only:
            raise HTTPException(status_code=403, detail="Panel is in read-only mode.")

    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        tables = db.get_tables()
        if not tables:
            return templates.TemplateResponse(
                "empty.html",
                {"request": request, "prefix": prefix, "title": title, "tables": []},
            )
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{prefix}/table/{tables[0].name}")

    @router.get("/table/{table_name}", response_class=HTMLResponse)
    async def table_view(
        request: Request,
        table_name: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        sort: str = Query(""),
        dir: str = Query("asc"),
        search: str = Query(""),
    ):
        table_info = db.get_table(table_name)
        if table_info is None:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

        # Per-column filter params: filter_<col>=<val>
        filters = {}
        for key, val in request.query_params.items():
            if key.startswith("filter_") and val:
                col = key[7:]
                filters[col] = val

        result = db.query_table(
            table_name,
            page=page,
            page_size=page_size,
            sort_col=sort or None,
            sort_dir=dir,
            search=search,
            filters=filters,
        )

        tables = db.get_tables()
        pk_col = next((c.name for c in table_info.columns if c.is_pk), None)
        col_map = {c.name: c for c in table_info.columns}

        return templates.TemplateResponse(
            "table.html",
            {
                "request": request,
                "prefix": prefix,
                "title": title,
                "tables": tables,
                "table_info": table_info,
                "result": result,
                "pk_col": pk_col,
                "col_map": col_map,
                "read_only": read_only,
                "filters": filters,
            },
        )

    @router.get("/table/{table_name}/row/{pk_val}", response_class=HTMLResponse)
    async def row_detail(request: Request, table_name: str, pk_val: str):
        table_info = db.get_table(table_name)
        if table_info is None:
            raise HTTPException(status_code=404)
        pk_col = next((c.name for c in table_info.columns if c.is_pk), None)
        if not pk_col:
            raise HTTPException(status_code=400, detail="Table has no primary key.")
        row = db.get_row(table_name, pk_col, pk_val)
        if row is None:
            raise HTTPException(status_code=404, detail="Row not found.")
        tables = db.get_tables()
        col_map = {c.name: c for c in table_info.columns}
        return templates.TemplateResponse(
            "row_detail.html",
            {
                "request": request,
                "prefix": prefix,
                "title": title,
                "tables": tables,
                "table_info": table_info,
                "row": row,
                "pk_col": pk_col,
                "col_map": col_map,
                "read_only": read_only,
            },
        )

    @router.post("/table/{table_name}/row/{pk_val}/delete")
    async def delete_row(request: Request, table_name: str, pk_val: str):
        _require_write()
        table_info = db.get_table(table_name)
        if table_info is None:
            raise HTTPException(status_code=404)
        pk_col = next((c.name for c in table_info.columns if c.is_pk), None)
        if not pk_col:
            raise HTTPException(status_code=400)
        db.delete_row(table_name, pk_col, pk_val)
        return JSONResponse({"ok": True})

    @router.post("/table/{table_name}/row/{pk_val}/update")
    async def update_row(request: Request, table_name: str, pk_val: str):
        _require_write()
        table_info = db.get_table(table_name)
        if table_info is None:
            raise HTTPException(status_code=404)
        pk_col = next((c.name for c in table_info.columns if c.is_pk), None)
        if not pk_col:
            raise HTTPException(status_code=400)
        form = await request.form()
        data = {k: v for k, v in form.items() if k != pk_col}
        db.update_row(table_name, pk_col, pk_val, data)
        return JSONResponse({"ok": True})

    @router.post("/table/{table_name}/insert")
    async def insert_row(request: Request, table_name: str):
        _require_write()
        table_info = db.get_table(table_name)
        if table_info is None:
            raise HTTPException(status_code=404)
        form = await request.form()
        pk_col = next((c.name for c in table_info.columns if c.is_pk), None)
        data = {}
        for k, v in form.items():
            if k == pk_col and not v:
                continue
            if v != "":
                data[k] = v
        new_id = db.insert_row(table_name, data)
        return JSONResponse({"ok": True, "id": new_id})

    # ------------------------------------------------------------------
    # Polling endpoint for auto-refresh
    # ------------------------------------------------------------------

    @router.get("/api/fingerprint")
    async def fingerprint():
        return JSONResponse(db.get_db_fingerprint())

    # ------------------------------------------------------------------
    # Partial HTML endpoint for HTMX table body refresh
    # ------------------------------------------------------------------

    @router.get("/table/{table_name}/rows", response_class=HTMLResponse)
    async def table_rows_partial(
        request: Request,
        table_name: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        sort: str = Query(""),
        dir: str = Query("asc"),
        search: str = Query(""),
    ):
        table_info = db.get_table(table_name)
        if table_info is None:
            raise HTTPException(status_code=404)

        filters = {}
        for key, val in request.query_params.items():
            if key.startswith("filter_") and val:
                filters[key[7:]] = val

        result = db.query_table(
            table_name,
            page=page,
            page_size=page_size,
            sort_col=sort or None,
            sort_dir=dir,
            search=search,
            filters=filters,
        )
        pk_col = next((c.name for c in table_info.columns if c.is_pk), None)
        col_map = {c.name: c for c in table_info.columns}

        return templates.TemplateResponse(
            "partials/rows.html",
            {
                "request": request,
                "prefix": prefix,
                "table_info": table_info,
                "result": result,
                "pk_col": pk_col,
                "col_map": col_map,
                "read_only": read_only,
                "filters": filters,
            },
        )

    return router
