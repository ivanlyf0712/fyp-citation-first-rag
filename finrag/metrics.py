"""Measurement primitives, each traceable to a published convention.

The point of this module is that the report does not invent its statistics.
Every function names where the method comes from and what it assumes.

| Function | Method | Source |
|---|---|---|
| `wilson` | score interval for a binomial proportion | Wilson (1927); recommended over the normal approximation for small n by Brown, Cai & DasGupta (2001) |
| `mcnemar` | exact paired test on discordant pairs | McNemar (1947); exact binomial form for small samples |
| `ndcg_at_k` | graded relevance, log discount | Järvelin & Kekäläinen (2002); the k=10 convention follows BEIR (Thakur et al., 2021) |
| `recall_at_k`, `mrr` | standard retrieval summaries | TREC/BEIR practice |
| `citation_precision_recall` | whether cited spans support and cover the answer | ALCE (Gao et al., 2023) |
| `acr` | dispersion of answers across readers | this project (see docs/METRICS.md) |

Nothing here is approximate where it can be exact: proportions carry intervals,
and paired comparisons use the exact test rather than a normal approximation,
because the number of discordant pairs is small by construction.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


# --------------------------------------------------------------------------
# Proportions
# --------------------------------------------------------------------------
def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred here because several cells in the results have n below 30, where
    the normal approximation produces intervals that run outside [0, 1] and
    understate coverage. See Brown, Cai & DasGupta (2001), *Interval Estimation
    for a Binomial Proportion*, Statistical Science 16(2).
    """
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def fmt_interval(successes: int, n: int) -> str:
    """`k/n (lo–hi)` with the interval as percentages, for a results table."""
    if n == 0:
        return "0/0"
    lo, hi = wilson(successes, n)
    return f"{successes}/{n} ({lo:.0%}–{hi:.0%})"


# --------------------------------------------------------------------------
# Paired comparison
# --------------------------------------------------------------------------
def mcnemar(b: int, c: int) -> tuple[float, float]:
    """Exact McNemar test on the discordant pairs.

    ``b`` = cases where condition A succeeded and B failed; ``c`` the reverse.
    Returns (statistic, p). The p-value is the exact two-sided binomial test,
    which is the correct form when b + c is small — as it is here, because the
    two pipelines agree on most questions.
    """
    n = b + c
    if n == 0:
        return (0.0, 1.0)
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / (2 ** n)
    p = min(1.0, 2 * tail)
    # chi-square form with continuity correction, reported for familiarity
    chi2 = (abs(b - c) - 1) ** 2 / n if n else 0.0
    return (chi2, p)


def sign_test(better: int, worse: int) -> float:
    """Exact two-sided sign test over discordant units.

    Used when the unit of independence is the *question*, not the (question, role)
    pair: six roles answering the same question share its evidence, so their
    outcomes are correlated and McNemar's p-value over pairs is optimistic. The
    sign test asks only how many questions moved in each direction.
    """
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------
def dcg(relevances: Sequence[float]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(relevances))


def ndcg_at_k(ranked_ids: Sequence[str], relevant: Iterable[str], k: int = 10) -> float:
    """Binary-relevance nDCG@k, the BEIR convention (k = 10)."""
    rel = set(relevant)
    if not rel:
        return 0.0
    gains = [1.0 if rid in rel else 0.0 for rid in ranked_ids[:k]]
    ideal = [1.0] * min(len(rel), k)
    denom = dcg(ideal)
    return dcg(gains) / denom if denom else 0.0


def recall_at_k(ranked_ids: Sequence[str], relevant: Iterable[str], k: int = 10) -> float:
    rel = set(relevant)
    if not rel:
        return 0.0
    return len(set(ranked_ids[:k]) & rel) / len(rel)


def reciprocal_rank(ranked_ids: Sequence[str], relevant: Iterable[str]) -> float:
    rel = set(relevant)
    for i, rid in enumerate(ranked_ids, start=1):
        if rid in rel:
            return 1.0 / i
    return 0.0


# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------
def citation_precision_recall(cited: Iterable[str],
                              needed: Iterable[str]) -> tuple[float, float]:
    """ALCE-style citation precision and recall over evidence identifiers.

    *Precision* is the share of cited evidence that was actually needed;
    *recall* is the share of needed evidence that was cited. ALCE (Gao et al.,
    2023, *Enabling Large Language Models to Generate Text with Citations*)
    reports the same two quantities per statement; here the statement is the
    whole answer, which is the right granularity for a single numeric claim.
    """
    cited_set, needed_set = set(cited), set(needed)
    if not cited_set and not needed_set:
        return (1.0, 1.0)
    precision = len(cited_set & needed_set) / len(cited_set) if cited_set else 0.0
    recall = len(cited_set & needed_set) / len(needed_set) if needed_set else 1.0
    return (precision, recall)


# --------------------------------------------------------------------------
# Agreement
# --------------------------------------------------------------------------
def acr(values: Sequence[int | None], roles: int) -> tuple[float, float]:
    """Answer Consistency Ratio, raw and normalised.

    Raw ACR is ``1 - distinct/roles``, which is bounded above at
    ``1 - 1/roles`` and therefore cannot reach 1. Normalised ACR is
    ``1 - (distinct - 1)/(roles - 1)``, which maps perfect agreement to 1.

    Reported alongside the distribution rather than instead of it: a single
    dispersion number hides *which* answers were given, and in this project the
    interesting part is that every answer is a different partial sum.
    """
    answered = [v for v in values if v is not None]
    distinct = len(set(answered))
    if roles <= 1:
        return (1.0, 1.0)
    raw = 1 - distinct / roles
    norm = 1 - (distinct - 1) / (roles - 1)
    return (round(raw, 4), round(norm, 4))


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
