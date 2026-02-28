"""Integration tests for the FastAPI router."""

import sqlite3

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from sqlite_webpanel import mount_sqlite_panel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL,
            in_stock INTEGER DEFAULT 1
        )
    """)
    conn.execute("INSERT INTO products (name, price, in_stock) VALUES ('Widget', 9.99, 1)")
    conn.execute("INSERT INTO products (name, price, in_stock) VALUES ('Gadget', 19.99, 0)")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def app(db_path):
    application = FastAPI()
    mount_sqlite_panel(application, db_path=db_path, prefix="/admin")
    return application


@pytest.fixture
def readonly_app(db_path):
    application = FastAPI()
    mount_sqlite_panel(application, db_path=db_path, prefix="/admin", read_only=True)
    return application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def readonly_client(readonly_app):
    async with AsyncClient(
        transport=ASGITransport(app=readonly_app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redirect_to_first_table(client):
    resp = await client.get("/admin/", follow_redirects=False)
    # Should be HTML (redirect or table page)
    assert resp.status_code in (200, 307, 302)


@pytest.mark.asyncio
async def test_table_view(client):
    resp = await client.get("/admin/table/products")
    assert resp.status_code == 200
    assert "products" in resp.text


@pytest.mark.asyncio
async def test_table_not_found(client):
    resp = await client.get("/admin/table/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_table_search(client):
    resp = await client.get("/admin/table/products?search=widget")
    assert resp.status_code == 200
    assert "Widget" in resp.text


@pytest.mark.asyncio
async def test_table_pagination(client):
    resp = await client.get("/admin/table/products?page=1&page_size=1")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_row_detail(client):
    resp = await client.get("/admin/table/products/row/1")
    assert resp.status_code == 200
    assert "Widget" in resp.text


@pytest.mark.asyncio
async def test_insert_row(client):
    resp = await client.post(
        "/admin/table/products/insert",
        data={"name": "Doohickey", "price": "4.99", "in_stock": "1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_update_row(client):
    resp = await client.post(
        "/admin/table/products/row/1/update",
        data={"name": "Widget Pro", "price": "14.99"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_delete_row(client):
    resp = await client.post("/admin/table/products/row/2/delete")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_fingerprint_endpoint(client):
    resp = await client.get("/admin/api/fingerprint")
    assert resp.status_code == 200
    data = resp.json()
    assert "products" in data
    assert isinstance(data["products"], int)


@pytest.mark.asyncio
async def test_readonly_blocks_insert(readonly_client):
    resp = await readonly_client.post(
        "/admin/table/products/insert",
        data={"name": "Blocked"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_readonly_blocks_delete(readonly_client):
    resp = await readonly_client.post("/admin/table/products/row/1/delete")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_partial_rows_endpoint(client):
    resp = await client.get("/admin/table/products/rows")
    assert resp.status_code == 200
    assert "Widget" in resp.text
