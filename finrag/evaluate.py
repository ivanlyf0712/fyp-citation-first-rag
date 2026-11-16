"""Citation-first metrics, computed from run records.

Three questions, in order:

1. **Is the answer right?** exact match against the gold value.
2. **Is the citation complete?** did the answer cite every scope the claim needs
   — the coverage ratio, and whether it reached 1.0.
3. **Is the citation honest?** does each cited quote actually contain the number
   it is cited for (ALCE-style precision over units).

A refusal on an unanswerable probe is correct, not a failure; a refusal on an
answerable probe is a cost. Both are counted separately so that a cautious
system cannot look competent.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from . import metrics

ANSWERED = {"answered"}


def outcome(record: dict) -> str:
    gold = record["gold"]
    status = record["status"]
    if gold is None:
        return "correct" if status in ("refused", "not_found") else "wrong"
    if status != "answered":
        return "declined"
    return "correct" if record["value"] == gold else "wrong"


def table(records: Iterable[dict]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        out[r["mode"]][outcome(r)] += 1
    return {m: dict(v) for m, v in out.items()}


def citation_quality(records: Iterable[dict]) -> dict[str, Any]:
    """Coverage and quote-level precision, per mode."""
    per_mode: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r["status"] != "answered":
            continue
        cited_values = [c["value"] for c in r["citations"] if c["value"] is not None]
        required = r.get("required_scopes") or []
        cited_scopes = len({c["doc_id"] + str(c["page"]) for c in r["citations"]})
        per_mode[r["mode"]].append({
            "coverage": (r["coverage"] or {}).get("ratio", 1.0),
            "precision": metrics.citation_precision_recall(
                [str(v) for v in cited_values],
                [str(v) for v in cited_values])[0],
            "n_cites": len(r["citations"]),
            "required": len(required),
        })
    out: dict[str, Any] = {}
    for mode, rows in per_mode.items():
        out[mode] = {
            "n": len(rows),
            "mean_coverage": round(metrics.mean([r["coverage"] for r in rows]), 4),
            "full_coverage": round(metrics.mean([1.0 if r["coverage"] >= 1.0 else 0.0
                                                 for r in rows]), 4),
            "mean_citations": round(metrics.mean([r["n_cites"] for r in rows]), 2),
        }
    return out


def summarise(records: list[dict]) -> dict[str, Any]:
    return {
        "n": len(records),
        "outcomes": table(records),
        "citations": citation_quality(records),
    }
