#!/usr/bin/env python3
"""Multi-hop questions: two rows, one ratio, computed by code.

A question like "what was the implied tax rate" cannot be answered by selecting
one row. The graph links labels to rows, the code fetches the two values, and the
arithmetic is deterministic — the model is not asked to divide.

    python scripts/multihop_eval.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import value_matches  # noqa: E402
from finrag.graph import UnitGraph, is_primary  # noqa: E402
from finrag.ingest import parse_numbers  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.retrieve import Bm25Index, Chunk  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402

QUESTIONS = [
    ("What was the implied tax rate on the Group's profit?",
     ["income tax expense", "profit before taxation"], "ratio", 0.014478),
    ("What share of operating income went to operating expenses?",
     ["operating expenses", "operating income"], "ratio", 0.41161),
    ("How much of operating income came from net interest income?",
     ["net interest income", "operating income"], "ratio", 0.60995),
    ("What share of operating income was absorbed by impairment?",
     ["impairment losses on assets", "operating income"], "ratio", 0.37907),
    ("What margin of operating income became net profit?",
     ["net profit", "operating income"], "ratio", 0.20626),
]


def value_of(quote: str) -> float | None:
    for cell in quote.split(" | ")[1:]:
        numbers, _ = parse_numbers(cell)
        if numbers:
            return numbers[0]
    return None


def main() -> int:
    raw = attach_sections(load_jsonl(Path("annotations/corpus/units.jsonl")))
    rows = [SimpleNamespace(**u) for u in raw if u.get("source") == "docling-row"]
    graph = UnitGraph.build(rows)

    index = Bm25Index()
    for u in rows:
        index.add(Chunk(doc_id=u.unit_id, page=u.page,
                        text=u.quote.split(" | ")[0]))
    index.finalize()
    by_id = {u.unit_id: u for u in rows}

    def best_row(label: str):
        ranked = index.ranked_docs(label, k=20)
        candidates = [by_id[uid] for uid in ranked if uid in by_id]
        primary = [u for u in candidates if is_primary(u)]
        return (primary or candidates or [None])[0]

    lines = ["# Multi-hop questions", "",
             "Two rows are located by their labels, the ratio is computed by code, "
             "and both units are cited.", "",
             "| question | rows | value | gold | ok |", "|---|---|---|---|---|"]
    hits = 0
    for question, labels, _op, gold in QUESTIONS:
        picked = [best_row(label) for label in labels]
        if not all(picked):
            lines.append(f"| {question} | not found | — | {gold:.4f} | ✗ |")
            continue
        values = [value_of(u.quote) for u in picked]
        if not all(v is not None for v in values):
            lines.append(f"| {question} | not found | — | {gold:.4f} | ✗ |")
            continue
        ratio = abs(values[0]) / abs(values[1]) if values[1] else 0.0
        ok = abs(ratio - gold) < 0.001
        hits += ok
        rows_txt = " + ".join(f"p{u.page}" for u in picked)
        lines.append(f"| {question} | {rows_txt} | {ratio:.4f} | {gold:.4f} | "
                     f"{'✓' if ok else '✗'} |")

    lines += ["", f"Correct: **{hits}/{len(QUESTIONS)}**"]
    Path("MULTIHOP.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
