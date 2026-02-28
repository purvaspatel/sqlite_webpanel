"""Tests for smart cell renderers."""

import pytest

from sqlite_webpanel.renderers import render_cell


def test_null_renders_null_span():
    html = render_cell(None)
    assert "cell-null" in html
    assert "NULL" in html


def test_boolean_true():
    html = render_cell("1", "BOOLEAN")
    assert "badge-true" in html
    assert "true" in html


def test_boolean_false():
    html = render_cell("0", "BOOLEAN")
    assert "badge-false" in html
    assert "false" in html


def test_integer_cell():
    html = render_cell(42, "INTEGER")
    assert "cell-number" in html
    assert "42" in html


def test_json_cell():
    html = render_cell('{"key": "value"}', "TEXT")
    assert "json-cell" in html
    assert "JSON" in html


def test_image_url():
    html = render_cell("https://example.com/photo.jpg")
    assert "img-thumb" in html
    assert "https://example.com/photo.jpg" in html


def test_file_url():
    html = render_cell("https://example.com/report.pdf")
    assert "file-link" in html
    assert "report.pdf" in html


def test_generic_url():
    html = render_cell("https://example.com/page")
    assert "url-link" in html


def test_long_text_truncated():
    long = "x" * 200
    html = render_cell(long)
    assert "long-text" in html
    assert "expand-btn" in html


def test_short_text_plain():
    html = render_cell("Hello, world!")
    assert "long-text" not in html
    assert "Hello, world!" in html


def test_xss_escaped():
    html = render_cell("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_none_value():
    html = render_cell(None, "INTEGER")
    assert "NULL" in html
