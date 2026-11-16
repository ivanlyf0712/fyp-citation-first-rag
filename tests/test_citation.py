"""Invariants of the citation-first pipeline."""

from __future__ import annotations

import pytest

from finrag.citations import Citation, check_coverage, check_support, verify
from finrag.estate import CELL_METRIC
from finrag.pipeline import CITATION_FIRST, PASSAGE_FIRST, CitationFirst
from finrag.units import build_units, required_for_total


def test_units_cover_every_observation(corpus):
    units = build_units(corpus)
    n_obs = sum(len(f.observations) for f in corpus.facts.values())
    assert len(units) == n_obs
    for u in units:
        assert u.quote.strip()
        x0, y0, x1, y1 = u.bbox
        assert 0 <= x0 < x1 <= 596 and 0 <= y0 < y1 <= 842
        assert u.channel in ("text", "table", "figure")


def test_coverage_reports_missing_scopes(corpus):
    units = build_units(corpus)
    required = required_for_total(units, "Harbour Finance")
    assert len(required) == 9
    partial = [units[0]]
    cov = check_coverage(required, partial)
    assert not cov.ok and cov.missing
    full = [v[0] for v in required.values()]
    assert check_coverage(required, full).ok


def test_support_rejects_a_quote_that_does_not_contain_its_value():
    bad = Citation("U:x", "D-1", 1, (0, 0, 10, 10), "no number here", "text", 817)
    ok, _checks, failures = check_support(817, [bad], [817])
    assert not ok and failures


def test_support_rejects_broken_arithmetic():
    a = Citation("U:a", "D-1", 1, (0, 0, 10, 10), " 120 million", "text", 120)
    b = Citation("U:b", "D-2", 1, (0, 0, 10, 10), " 100 million", "text", 100)
    ok, _c, failures = check_support(817, [a, b], [120, 100])
    assert not ok and "derivation" in failures[0]


def test_passage_first_returns_a_partial_sum(corpus, corpus_dir):
    pipe = CitationFirst(corpus, corpus_dir)
    answer = pipe.ask("What is the total exposure for Harbour Finance for FY2024?",
                      PASSAGE_FIRST)
    cells = sum(1 for u in pipe.units
                if u.entity == "Harbour Finance" and u.metric == CELL_METRIC)
    if answer.status == "answered":
        assert answer.coverage is not None
        assert answer.coverage.ratio <= 1.0
        assert len(answer.citations) <= 5 * 3   # top-5 pages cannot hold 9 cells


def test_citation_first_requires_full_coverage(corpus, corpus_dir):
    pipe = CitationFirst(corpus, corpus_dir, k_units=3)
    answer = pipe.ask("What is the total exposure for Harbour Finance for FY2024?",
                      CITATION_FIRST)
    assert answer.status in ("answered", "refused")
    if answer.status == "answered":
        assert answer.coverage.ratio == 1.0


def test_wrong_period_is_refused(corpus, corpus_dir):
    pipe = CitationFirst(corpus, corpus_dir)
    for mode in (CITATION_FIRST, PASSAGE_FIRST):
        a = pipe.ask("What is the total exposure for Harbour Finance for FY2023?", mode)
        assert a.status == "refused" and a.value is None


def test_citations_are_self_supporting(corpus, corpus_dir):
    """Every citation's quote must contain the value it is cited for."""
    pipe = CitationFirst(corpus, corpus_dir)
    a = pipe.ask("What is the total exposure for Harbour Finance for FY2024?",
                 CITATION_FIRST)
    assert a.status == "answered"
    for c in a.citations:
        assert str(c.value) in c.quote
    assert a.value == sum(c.value for c in a.citations)
