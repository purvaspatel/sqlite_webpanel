"""
Core database layer — all SQLite interactions live here.
Completely decoupled from the web layer.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
def __init__(self, db_path: str | Path) -> None:
    self.db_path = Path(db_path).resolve()

@dataclass
class ColumnInfo:
    name: str
    type: str
    notnull: bool
    default_value: Any
    is_pk: bool

    @property
    def display_type(self) -> str:
        t = self.type.upper()
        if not t:
            return "TEXT"
        for prefix in ("INT", "INTEGER", "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT"):
            if t.startswith(prefix):
                return "INTEGER"
        if any(t.startswith(p) for p in ("REAL", "DOUBLE", "FLOAT", "NUMERIC", "DECIMAL")):
            return "REAL"
        if "BLOB" in t:
            return "BLOB"
        if "BOOL" in t:
            return "BOOLEAN"
        return "TEXT"


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: int = 0


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    total: int
    page: int
    page_size: int
    table: str
    sort_col: str | None = None
    sort_dir: str = "asc"
    search: str = ""
    filters: dict[str, str] = field(default_factory=dict)

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 1
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def page_range(self) -> list[int]:
        """Return page numbers to show in pagination (with ellipsis markers as -1)."""
        total = self.total_pages
        current = self.page
        if total <= 7:
            return list(range(1, total + 1))
        pages = set()
        pages.update([1, 2, total - 1, total])
        for d in range(-2, 3):
            p = current + d
            if 1 <= p <= total:
                pages.add(p)
        result = []
        prev = None
        for p in sorted(pages):
            if prev is not None and p - prev > 1:
                result.append(-1)
            result.append(p)
            prev = p
        return result


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]*$")


def _safe_identifier(name: str) -> str:
    """Validate and quote a SQLite identifier."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return f'"{name}"'


_SAFE_DIRECTION = {"asc", "desc"}


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------

class Database:
    """
    Thin, safe wrapper around a SQLite file.

    All public methods that accept user-supplied values use parameterised
    queries or strict identifier validation — never raw string interpolation
    of user input.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    def get_tables(self) -> list[TableInfo]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
            tables = []
            for row in cur.fetchall():
                name = row["name"]
                cols = self._get_columns(conn, name)
                count = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {_safe_identifier(name)}"
                ).fetchone()["c"]
                tables.append(TableInfo(name=name, columns=cols, row_count=count))
            return tables

    def get_table(self, table_name: str) -> TableInfo | None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            if not exists:
                return None
            cols = self._get_columns(conn, table_name)
            count = conn.execute(
                f"SELECT COUNT(*) AS c FROM {_safe_identifier(table_name)}"
            ).fetchone()["c"]
            return TableInfo(name=table_name, columns=cols, row_count=count)

    def _get_columns(self, conn: sqlite3.Connection, table_name: str) -> list[ColumnInfo]:
        cur = conn.execute(f"PRAGMA table_info({_safe_identifier(table_name)})")
        return [
            ColumnInfo(
                name=r["name"],
                type=r["type"],
                notnull=bool(r["notnull"]),
                default_value=r["dflt_value"],
                is_pk=bool(r["pk"]),
            )
            for r in cur.fetchall()
        ]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query_table(
        self,
        table_name: str,
        page: int = 1,
        page_size: int = 50,
        sort_col: str | None = None,
        sort_dir: str = "asc",
        search: str = "",
        filters: dict[str, str] | None = None,
    ) -> QueryResult:
        """
        Fetch a page of rows with optional sorting, full-text search, and
        per-column filters.  All user-supplied values are bound as parameters.
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50
        sort_dir = sort_dir.lower() if sort_dir.lower() in _SAFE_DIRECTION else "asc"
        filters = filters or {}

        tbl = _safe_identifier(table_name)

        with self._connect() as conn:
            cols_info = self._get_columns(conn, table_name)
            col_names = [c.name for c in cols_info]

            where_clauses: list[str] = []
            params: list[Any] = []

            # Full-text search across all text-ish columns
            if search:
                text_cols = [
                    c for c in cols_info if "INT" not in c.type.upper() and "REAL" not in c.type.upper()
                ]
                if text_cols:
                    search_parts = [
                        f"CAST({_safe_identifier(c.name)} AS TEXT) LIKE ?"
                        for c in text_cols
                    ]
                    where_clauses.append("(" + " OR ".join(search_parts) + ")")
                    params.extend([f"%{search}%"] * len(text_cols))

            # Per-column filters
            for col, val in filters.items():
                if col in col_names and val:
                    where_clauses.append(f"CAST({_safe_identifier(col)} AS TEXT) LIKE ?")
                    params.append(f"%{val}%")

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # Total count
            count_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM {tbl} {where_sql}", params
            ).fetchone()
            total = count_row["c"]

            # Order
            order_sql = ""
            if sort_col and sort_col in col_names:
                order_sql = f"ORDER BY {_safe_identifier(sort_col)} {sort_dir.upper()}"

            # Pagination
            offset = (page - 1) * page_size
            data_cur = conn.execute(
                f"SELECT * FROM {tbl} {where_sql} {order_sql} LIMIT ? OFFSET ?",
                params + [page_size, offset],
            )
            rows = [tuple(r) for r in data_cur.fetchall()]

            return QueryResult(
                columns=col_names,
                rows=rows,
                total=total,
                page=page,
                page_size=page_size,
                table=table_name,
                sort_col=sort_col,
                sort_dir=sort_dir,
                search=search,
                filters=filters,
            )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def insert_row(self, table_name: str, data: dict[str, Any]) -> int:
        tbl = _safe_identifier(table_name)
        cols = [_safe_identifier(k) for k in data]
        placeholders = ", ".join("?" * len(data))
        sql = f"INSERT INTO {tbl} ({', '.join(cols)}) VALUES ({placeholders})"
        with self._connect() as conn:
            cur = conn.execute(sql, list(data.values()))
            conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def update_row(self, table_name: str, pk_col: str, pk_val: Any, data: dict[str, Any]) -> None:
        tbl = _safe_identifier(table_name)
        set_parts = ", ".join(f"{_safe_identifier(k)} = ?" for k in data)
        pk = _safe_identifier(pk_col)
        sql = f"UPDATE {tbl} SET {set_parts} WHERE {pk} = ?"
        with self._connect() as conn:
            conn.execute(sql, list(data.values()) + [pk_val])
            conn.commit()

    def delete_row(self, table_name: str, pk_col: str, pk_val: Any) -> None:
        tbl = _safe_identifier(table_name)
        pk = _safe_identifier(pk_col)
        sql = f"DELETE FROM {tbl} WHERE {pk} = ?"
        with self._connect() as conn:
            conn.execute(sql, [pk_val])
            conn.commit()

    def get_row(self, table_name: str, pk_col: str, pk_val: Any) -> dict | None:
        tbl = _safe_identifier(table_name)
        pk = _safe_identifier(pk_col)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {tbl} WHERE {pk} = ?", [pk_val]
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # DB metadata for polling
    # ------------------------------------------------------------------

    def get_db_fingerprint(self) -> dict[str, int]:
        """Return {table_name: row_count} for change detection."""
        with self._connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            result = {}
            for t in tables:
                name = t["name"]
                count = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {_safe_identifier(name)}"
                ).fetchone()["c"]
                result[name] = count
            return result

    # ------------------------------------------------------------------
    # Raw SQL execution (for future extensibility)
    # ------------------------------------------------------------------

    def execute_safe_query(self, sql: str) -> tuple[list[str], list[tuple]]:
        """
        Execute a read-only SQL query.  Raises if it looks like a write.
        """
        normalised = sql.strip().upper()
        if not normalised.startswith("SELECT"):
            raise ValueError("Only SELECT statements are allowed here.")
        forbidden = ("DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "ATTACH")
        for kw in forbidden:
            if re.search(rf"\b{kw}\b", normalised):
                raise ValueError(f"Forbidden keyword: {kw}")
        with self._connect() as conn:
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [tuple(r) for r in cur.fetchall()]
            return cols, rows
