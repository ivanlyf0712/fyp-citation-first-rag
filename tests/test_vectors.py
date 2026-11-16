"""Tests for the embedding index, without loading a model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from finrag.vectors import UnitIndex, unit_contexts


@dataclass
class FakeUnit:
    unit_id: str
    doc: str
    page: int
    quote: str
    bbox: tuple = (0, 0, 10, 10)
    source: str = "text-layer"


def test_table_rows_get_their_header_prepended():
    units = [
        FakeUnit("H", "a.pdf", 1, "2024 | 2023 | Change", bbox=(0, 90, 100, 98),
                 source="docling-row"),
        FakeUnit("R", "a.pdf", 1, "Net profit | 5,255,815", bbox=(0, 50, 100, 58),
                 source="docling-row"),
        FakeUnit("T", "a.pdf", 1, "Some prose about the year.", bbox=(0, 10, 100, 20)),
    ]
    contexts = dict(unit_contexts(units))
    assert contexts["R"].startswith("2024 | 2023 | Change :: ")
    assert contexts["H"].startswith("2024 | 2023 | Change")
    assert contexts["T"] == "Some prose about the year."


def test_save_and_load_round_trip(tmp_path):
    index = UnitIndex(unit_ids=["U:a", "U:b"],
                      vectors=np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    npz, manifest = index.save(tmp_path)
    assert npz.exists() and manifest.exists()
    again = UnitIndex.load(npz)
    assert again.unit_ids == ["U:a", "U:b"]
    assert np.allclose(again.vectors, index.vectors)
