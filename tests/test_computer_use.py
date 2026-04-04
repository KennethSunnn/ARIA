"""Unit tests for Computer Use helpers (no real mouse movement)."""

import json

import pytest

from automation import computer_use


def test_virtual_screen_metrics_has_keys():
    m = computer_use.virtual_screen_metrics()
    assert {"left", "top", "width", "height"} <= m.keys()
    assert m["width"] > 0 and m["height"] > 0


def test_point_in_allow_regions():
    assert computer_use.point_in_allow_regions(5, 5, [(0, 0, 10, 10)]) is True
    assert computer_use.point_in_allow_regions(50, 50, [(0, 0, 10, 10)]) is False
    assert computer_use.point_in_allow_regions(1, 1, []) is True


def test_resolve_normalized_1000():
    m = {"left": 0, "top": 0, "width": 1000, "height": 500}
    p = computer_use.resolve_screen_point({"x": 500, "y": 250, "coord_space": "normalized_1000"}, metrics=m)
    assert p == (500, 125)


def test_ensure_mutation_allow_regions(monkeypatch):
    monkeypatch.setenv("ARIA_COMPUTER_USE_ALLOW_REGIONS", json.dumps([[0, 0, 10, 10]]))
    monkeypatch.delenv("ARIA_COMPUTER_USE_BLOCK_TITLE_KEYWORDS", raising=False)
    monkeypatch.setenv("ARIA_COMPUTER_USE", "1")
    ok, _ = computer_use.ensure_mutation_allowed(5, 5)
    assert ok is True
    ok2, reason = computer_use.ensure_mutation_allowed(20, 20)
    assert ok2 is False
    assert "allow_regions" in reason


def test_run_screenshot_info_disabled(monkeypatch):
    monkeypatch.setenv("ARIA_COMPUTER_USE", "0")
    r = computer_use.run_screenshot_info({})
    assert r.get("success") is False
