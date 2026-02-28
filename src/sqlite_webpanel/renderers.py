"""
Smart cell renderers — turn raw SQLite values into rich HTML snippets.
Each renderer returns a safe HTML string (Jinja2 Markup-compatible).
"""

from __future__ import annotations

import json
import re
from typing import Any

# URL regex
_URL_RE = re.compile(
    r"^(https?://[^\s]{6,})",
    re.IGNORECASE,
)

# Image extension check
_IMAGE_EXT = re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)(\?.*)?$", re.IGNORECASE)

# File extension check
_FILE_EXT = re.compile(
    r"\.(pdf|doc|docx|xls|xlsx|csv|txt|zip|gz|tar|mp4|mp3|mov|avi|md)(\?.*)?$",
    re.IGNORECASE,
)

# Long text threshold
_LONG_TEXT_THRESHOLD = 120


def _escape(val: str) -> str:
    """Minimal HTML escaping."""
    return (
        str(val)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def render_cell(value: Any, col_type: str = "TEXT") -> str:
    """
    Return an HTML snippet for a cell value.
    The display_type from ColumnInfo should be passed as col_type.
    """
    if value is None:
        return '<span class="cell-null">NULL</span>'

    raw = str(value)

    # --- Boolean ---
    if col_type == "BOOLEAN" or raw.lower() in ("true", "false", "1", "0"):
        if raw in ("1", "true", "True"):
            return '<span class="badge badge-true">✓ true</span>'
        if raw in ("0", "false", "False"):
            return '<span class="badge badge-false">✗ false</span>'

    # --- Integer / Real ---
    if col_type in ("INTEGER", "REAL"):
        return f'<span class="cell-number">{_escape(raw)}</span>'

    # --- JSON ---
    if raw.strip().startswith(("{", "[")):
        try:
            parsed = json.loads(raw)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            escaped = _escape(pretty)
            return (
                f'<details class="json-cell">'
                f'<summary class="json-summary">JSON ▸</summary>'
                f'<pre class="json-pre">{escaped}</pre>'
                f'</details>'
            )
        except (json.JSONDecodeError, ValueError):
            pass

    # --- URL-like ---
    if _URL_RE.match(raw):
        url = _escape(raw)

        # Image preview
        if _IMAGE_EXT.search(raw):
            return (
                f'<span class="img-cell">'
                f'<a href="{url}" target="_blank" rel="noopener">'
                f'<img src="{url}" class="img-thumb" loading="lazy" alt="preview" '
                f'     onerror="this.parentElement.parentElement.innerHTML=\'<a href=&quot;{url}&quot; target=&quot;_blank&quot;>{url}</a>\'" />'
                f'</a>'
                f'</span>'
            )

        # File link
        if _FILE_EXT.search(raw):
            fname = raw.split("/")[-1].split("?")[0]
            return f'<a href="{url}" class="file-link" target="_blank" rel="noopener">📎 {_escape(fname)}</a>'

        # Generic link
        display = raw if len(raw) <= 50 else raw[:47] + "…"
        return f'<a href="{url}" class="url-link" target="_blank" rel="noopener">{_escape(display)}</a>'

    # --- Long text ---
    if len(raw) > _LONG_TEXT_THRESHOLD:
        preview = _escape(raw[:_LONG_TEXT_THRESHOLD])
        full = _escape(raw)
        uid = abs(hash(raw)) % 100000
        return (
            f'<span class="long-text">'
            f'  <span id="preview-{uid}">{preview}'
            f'    <button class="expand-btn" onclick="toggleText({uid})">… more</button>'
            f'  </span>'
            f'  <span id="full-{uid}" style="display:none">{full}'
            f'    <button class="expand-btn" onclick="toggleText({uid})"> less</button>'
            f'  </span>'
            f'</span>'
        )

    return _escape(raw)
