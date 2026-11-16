"""Tests for the marker."""

from __future__ import annotations

from finrag.real_eval import contains_value, mark, summarise

UNITS = {
    "U:a": {"unit_id": "U:a", "quote": "Net profit | 5,255,815 | 5,080,903",
            "value": 5255815.0},
    "U:b": {"unit_id": "U:b", "quote": "Operating income 25,481,589",
            "value": 25481589.0},
}


def test_contains_value_handles_commas_and_negatives():
    assert contains_value("Net profit 5,255,815", 5255815.0)
    assert contains_value("Operating expenses (10,488,740)", 10488740.0)
    assert not contains_value("nothing here", 42.0)
    assert not contains_value("5,255,815", None)


def test_mark_correct_single():
    row = mark({"qid": "Q1", "question": "net profit?", "gold_value": 5255815.0,
                "required_units": ["U:a"]}, UNITS)
    assert row["status"] == "correct" and row["support"] is True


def test_mark_sums_multiple_units():
    row = mark({"qid": "Q2", "question": "sum", "gold_value": 30737404.0,
                "required_units": ["U:a", "U:b"]}, UNITS)
    assert row["status"] == "correct" and row["answer"] == 30737404.0


def test_missing_evidence_is_not_a_wrong_answer():
    row = mark({"qid": "Q3", "question": "x", "gold_value": 1.0,
                "required_units": ["U:zzz"]}, UNITS)
    assert row["status"] == "missing_evidence"
    assert summarise([row])["missing_evidence"] == 1


def test_wrong_value_is_reported_as_wrong():
    row = mark({"qid": "Q4", "question": "x", "gold_value": 999.0,
                "required_units": ["U:a"]}, UNITS)
    assert row["status"] == "wrong"
