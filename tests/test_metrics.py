"""Tests for the measurement primitives.

Each test pins a property that a reader of RESULTS.md is entitled to assume:
intervals stay inside [0, 1], the paired test is symmetric, a perfect ranking
scores 1, and ACR behaves at its two extremes.
"""

from __future__ import annotations

import math

import pytest

from finrag import metrics


def test_wilson_stays_in_the_unit_interval():
    for k in range(0, 11):
        lo, hi = metrics.wilson(k, 10)
        assert 0.0 <= lo <= hi <= 1.0
        assert lo <= k / 10 <= hi


def test_wilson_at_extremes():
    assert metrics.wilson(0, 0) == (0.0, 1.0)
    lo, hi = metrics.wilson(0, 10)
    assert lo == 0.0 and 0.0 < hi < 0.4
    lo, hi = metrics.wilson(10, 10)
    assert hi == 1.0 and 0.6 < lo < 1.0


def test_wilson_narrows_with_n():
    narrow = metrics.wilson(50, 100)
    wide = metrics.wilson(5, 10)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_mcnemar_is_symmetric_and_pins_the_big_case():
    assert metrics.mcnemar(0, 0)[1] == 1.0
    assert metrics.mcnemar(5, 5)[1] == 1.0
    assert metrics.mcnemar(3, 7)[1] == pytest.approx(metrics.mcnemar(7, 3)[1])
    # 24 discordant pairs, all one way: vanishingly unlikely under the null
    assert metrics.mcnemar(24, 0)[1] < 1e-6


def test_ndcg_perfect_and_empty():
    assert metrics.ndcg_at_k(["a", "b"], {"a", "b"}, k=10) == pytest.approx(1.0)
    assert metrics.ndcg_at_k(["c", "d"], {"a", "b"}, k=10) == 0.0
    assert metrics.ndcg_at_k([], {"a"}, k=10) == 0.0
    assert metrics.ndcg_at_k(["x", "a"], {"a"}, k=10) == pytest.approx(
        1 / math.log2(3), rel=1e-6)


def test_recall_and_mrr():
    assert metrics.recall_at_k(["a", "x"], {"a", "b"}, k=10) == 0.5
    assert metrics.reciprocal_rank(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)


def test_citation_precision_recall():
    assert metrics.citation_precision_recall(["a", "b"], {"a", "b"}) == (1.0, 1.0)
    p, r = metrics.citation_precision_recall(["a", "z"], {"a", "b"})
    assert p == 0.5 and r == 0.5
    assert metrics.citation_precision_recall([], set()) == (1.0, 1.0)
    assert metrics.citation_precision_recall([], {"a"}) == (0.0, 0.0)


def test_acr_extremes():
    raw, norm = metrics.acr([817] * 6, 6)
    assert norm == 1.0 and raw == pytest.approx(1 - 1 / 6, rel=1e-3)
    raw, norm = metrics.acr([1, 2, 3, 4, 5, 6], 6)
    assert norm == 0.0 and raw == 0.0
