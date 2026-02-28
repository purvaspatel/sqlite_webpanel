"""Tests for the core database layer."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from sqlite_webpanel import Database, _safe_identifier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            active INTEGER DEFAULT 1,
            score REAL
        )
    """)
    conn.execute("INSERT INTO users (name, email, active, score) VALUES (?, ?, ?, ?)",
                 ("Alice", "alice@example.com", 1, 9.5))
    conn.execute("INSERT INTO users (name, email, active, score) VALUES (?, ?, ?, ?)",
                 ("Bob", "bob@example.com", 0, 7.2))
    conn.execute("INSERT INTO users (name, email, active, score) VALUES (?, ?, ?, ?)",
                 ("Charlie", None, 1, 8.1))
    conn.commit()
    conn.close()
    return Database(db_file)


# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------

def test_safe_identifier_valid():
    assert _safe_identifier("users") == '"users"'
    assert _safe_identifier("my_table") == '"my_table"'


def test_safe_identifier_rejects_injection():
    with pytest.raises(ValueError):
        _safe_identifier("users; DROP TABLE users--")
    with pytest.raises(ValueError):
        _safe_identifier("'badname'")


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

def test_get_tables(tmp_db):
    tables = tmp_db.get_tables()
    assert len(tables) == 1
    assert tables[0].name == "users"
    assert tables[0].row_count == 3


def test_get_table(tmp_db):
    table = tmp_db.get_table("users")
    assert table is not None
    assert table.name == "users"
    assert len(table.columns) == 5
    col_names = [c.name for c in table.columns]
    assert "id" in col_names
    assert "name" in col_names


def test_get_table_not_found(tmp_db):
    assert tmp_db.get_table("nonexistent") is None


def test_columns_pk(tmp_db):
    table = tmp_db.get_table("users")
    pk_cols = [c for c in table.columns if c.is_pk]
    assert len(pk_cols) == 1
    assert pk_cols[0].name == "id"


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def test_query_all(tmp_db):
    result = tmp_db.query_table("users")
    assert result.total == 3
    assert len(result.rows) == 3
    assert result.page == 1


def test_query_pagination(tmp_db):
    r1 = tmp_db.query_table("users", page=1, page_size=2)
    assert len(r1.rows) == 2
    assert r1.total == 3
    assert r1.total_pages == 2
    assert r1.has_next is True
    assert r1.has_prev is False

    r2 = tmp_db.query_table("users", page=2, page_size=2)
    assert len(r2.rows) == 1
    assert r2.has_prev is True
    assert r2.has_next is False


def test_query_search(tmp_db):
    result = tmp_db.query_table("users", search="alice")
    assert result.total == 1
    assert result.rows[0][1] == "Alice"


def test_query_sort_asc(tmp_db):
    result = tmp_db.query_table("users", sort_col="name", sort_dir="asc")
    names = [r[1] for r in result.rows]
    assert names == sorted(names)


def test_query_sort_desc(tmp_db):
    result = tmp_db.query_table("users", sort_col="name", sort_dir="desc")
    names = [r[1] for r in result.rows]
    assert names == sorted(names, reverse=True)


def test_query_filter(tmp_db):
    result = tmp_db.query_table("users", filters={"name": "Bob"})
    assert result.total == 1
    assert result.rows[0][1] == "Bob"


def test_query_sort_injection_rejected(tmp_db):
    # An unsafe sort col should not crash but produce no sort (falls through safe path)
    result = tmp_db.query_table("users", sort_col="id; DROP TABLE users--")
    # Rows should still be returned (just unsorted / safe fallback)
    assert result.total == 3


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def test_insert_and_get(tmp_db):
    new_id = tmp_db.insert_row("users", {"name": "Diana", "email": "d@example.com", "active": 1})
    assert new_id is not None
    row = tmp_db.get_row("users", "id", new_id)
    assert row is not None
    assert row["name"] == "Diana"


def test_update_row(tmp_db):
    tmp_db.update_row("users", "id", 1, {"name": "Alice Updated"})
    row = tmp_db.get_row("users", "id", 1)
    assert row["name"] == "Alice Updated"


def test_delete_row(tmp_db):
    tmp_db.delete_row("users", "id", 1)
    row = tmp_db.get_row("users", "id", 1)
    assert row is None
    result = tmp_db.query_table("users")
    assert result.total == 2


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------

def test_fingerprint(tmp_db):
    fp = tmp_db.get_db_fingerprint()
    assert "users" in fp
    assert fp["users"] == 3


# ---------------------------------------------------------------------------
# Safe query
# ---------------------------------------------------------------------------

def test_execute_safe_query(tmp_db):
    cols, rows = tmp_db.execute_safe_query("SELECT name FROM users ORDER BY name")
    assert cols == ["name"]
    assert len(rows) == 3


def test_execute_safe_query_rejects_writes(tmp_db):
    with pytest.raises(ValueError):
        tmp_db.execute_safe_query("DELETE FROM users")
    with pytest.raises(ValueError):
        tmp_db.execute_safe_query("DROP TABLE users")
