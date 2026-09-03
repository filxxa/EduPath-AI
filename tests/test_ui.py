"""Focused UI helper regressions."""
from __future__ import annotations

from pathlib import Path

import pytest

import ui


def test_inject_theme_emits_css_for_every_script_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        ui.st,
        "markdown",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    ui.inject_theme()
    ui.inject_theme()

    assert calls == [
        ((ui._EP_CSS,), {"unsafe_allow_html": True}),
        ((ui._EP_CSS,), {"unsafe_allow_html": True}),
    ]


def test_action_plan_uses_indexed_navigation_button_keys() -> None:
    page_source = (
        Path(__file__).resolve().parents[1] / "pages" / "6_Action_Plan.py"
    ).read_text(encoding="utf-8")

    assert "for index, action in enumerate(next_actions[:3]):" in page_source
    assert 'key=f"goto_{index}_{action[\'priority\']}_{action[\'target\']}"' in page_source


def test_theme_css_reserves_top_toolbar_clearance() -> None:
    """The dashboard header must not be clipped by Streamlit's ~60px top toolbar."""
    assert ".block-container {" in ui._EP_CSS
    assert "padding-top: 4.5rem !important" in ui._EP_CSS
