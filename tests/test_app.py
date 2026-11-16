"""Smoke tests for the annotation bench."""

from __future__ import annotations

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_annotate_mode_renders_and_asks_for_a_pdf():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Upload a PDF" in i.value for i in at.info)
