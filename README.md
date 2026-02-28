# sqlite-panel

> A plug-and-play SQLite admin panel for FastAPI — beautiful, fast, and intelligent by default.

![Python](https://img.shields.io/badge/python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Features

- **One-line mount** — works with any FastAPI app
- **Auto-discovery** — detects all tables and columns automatically
- **Smart cell rendering** — JSON formatting, inline image previews, boolean badges, long text expand/collapse, file & URL links
- **Pagination, sorting, filtering, search** — all built-in
- **Inline editing** — double-click any cell to edit in place
- **Real-time change detection** — toast notifications + auto-refresh when the DB changes
- **Read-only mode** — disable all writes with a single flag
- **Light & dark mode** — with smooth toggle and `localStorage` persistence
- **Keyboard shortcuts** — `/` to search, `n` for new row, `Esc` to close modals
- **SQL injection safe** — all user input is parameterised or strictly validated
- **Zero heavy dependencies** — HTMX for partial refreshes, vanilla JS, Geist font via Google Fonts

---

## Installation

```bash
pip install sqlite-panel
```

## Quick start

```python
from fastapi import FastAPI
from sqlite_webpanel import mount_sqlite_panel

app = FastAPI()

mount_sqlite_panel(app, db_path="app.db")
# → Visit http://localhost:8000/admin
```

### Options

```python
mount_sqlite_panel(
    app,
    db_path="app.db",   # Path to SQLite file (created if absent)
    prefix="/admin",    # URL prefix  (default: /admin)
    read_only=False,    # Disable all writes (default: False)
    title="My App DB",  # Panel title (default: SQLite Panel)
)
```

---

## Usage example

```python
# main.py
from fastapi import FastAPI
from sqlite_webpanel import mount_sqlite_panel
import sqlite3

app = FastAPI()

# Create some demo data
conn = sqlite3.connect("demo.db")
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
conn.execute("INSERT OR IGNORE INTO users VALUES (1,'Alice','alice@example.com')")
conn.commit()
conn.close()

mount_sqlite_panel(app, db_path="demo.db", title="Demo DB")

# uvicorn main:app --reload
```

---

## Development

```bash
git clone https://github.com/yourname/sqlite-panel
cd sqlite-panel
pip install -e ".[dev]"
pytest
```

---

## Architecture

```
sqlite_panel/
├── __init__.py        # Public API: mount_sqlite_panel
├── mount.py           # FastAPI mounting + static files
├── router.py          # All HTTP endpoints (web layer)
├── db.py              # Core DB logic (pure Python, no web deps)
├── renderers.py       # Smart cell → HTML conversion
├── static/
│   ├── panel.css      # All styles (CSS variables, light/dark)
│   └── panel.js       # Interactivity (vanilla JS)
└── templates/
    ├── base.html      # Layout with sidebar
    ├── table.html     # Table view with toolbar
    ├── row_detail.html
    ├── empty.html
    ├── redirect.html
    └── partials/
        └── rows.html  # HTMX partial for table body
```

**Key design decisions:**

- `db.py` has zero FastAPI/web imports — testable in isolation
- `renderers.py` has zero DB imports — pure value → HTML transformation
- All SQL uses parameterised queries or `_safe_identifier()` validation
- HTMX partial endpoints allow row refresh without full page reload
- Change detection via polling `/api/fingerprint` (row count hash)

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `n` | Open "New Row" modal |
| `Esc` | Close modal / cancel edit |
| Double-click cell | Inline edit |

---

## License

MIT
