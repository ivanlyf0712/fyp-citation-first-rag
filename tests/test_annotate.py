"""Tests for ingestion and the append-only annotation files."""

from __future__ import annotations

from pathlib import Path

from finrag import annotations
from finrag.ingest import DraftUnit, parse_numbers


def test_number_parsing():
    assert parse_numbers("Total exposure was HK$817 million") == ([817.0], "")
    assert parse_numbers("HK$ 1,234.5m") == ([1234.5], "")
    assert parse_numbers("no digits here") == ([], "no number")
    assert parse_numbers("2024 and 2025") == ([2024.0, 2025.0], "multiple numbers")
    # parentheses are negatives in financial statements
    assert parse_numbers("Operating expenses (10,488,740)") == ([-10488740.0], "")


def test_unit_ids_are_stable_and_content_addressed():
    kw = dict(doc="a.pdf", page=3, channel="text", bbox=(0, 0, 10, 10),
              quote="Revenue 42", value=42, numbers=(42.0,), value_flag="")
    a = DraftUnit(unit_id="U:x", **kw)
    b = DraftUnit(unit_id="U:x", **kw)
    assert a.as_dict() == b.as_dict()
    assert a.as_dict()["bbox"] == [0, 0, 10, 10]


def test_accept_is_idempotent(tmp_path: Path):
    path = tmp_path / "units.jsonl"
    unit = {"unit_id": "U:abc", "doc": "a.pdf", "page": 1,
            "bbox": [0, 0, 10, 10], "quote": "Revenue 42", "value": 42,
            "numbers": [42.0], "channel": "text", "value_flag": ""}
    assert annotations.accept_unit(path, unit) is True
    assert annotations.accept_unit(path, unit) is False
    rows = annotations.read_all(path)
    assert len(rows) == 1 and rows[0]["verified"] is True
    assert "accepted_at" in rows[0]


def test_questions_append_and_reference_units(tmp_path: Path):
    path = tmp_path / "questions.jsonl"
    annotations.add_question(path, "Q001", "What is the total?", 817.0,
                             ["U:abc", "U:def"], "a.pdf")
    rows = annotations.read_all(path)
    assert rows[0]["required_units"] == ["U:abc", "U:def"]
    assert rows[0]["gold_value"] == 817.0


def test_crop_of_a_corpus_unit_is_non_empty(corpus, corpus_dir):
    from finrag.ui import crop_region

    unit = build_first_unit(corpus)
    img = crop_region(corpus_dir, "corpus/" + unit["doc"], unit["page"], tuple(unit["bbox"]))
    assert img.size[0] > 0 and img.size[1] > 0


def build_first_unit(corpus):
    for fact in corpus.facts.values():
        obs = fact.observations[0]
        return {"doc": obs.doc_id + ".pdf", "page": obs.page, "bbox": list(obs.bbox)}
    raise AssertionError("corpus has no units")
