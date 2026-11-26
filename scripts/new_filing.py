#!/usr/bin/env python3
"""Turn a parsed filing into a question set, mechanically.

    python scripts/new_filing.py --units annotations/corpus/other_units.jsonl \
        --out annotations/questions_other.jsonl

Parsing stays in build_unit_corpus.py (one page ~5 s). This maps a fixed list of
financial concepts onto rows by label, takes the value from each row, and writes
questions in the same format the scorer expects. The mapping is printed so it can
be reviewed before the questions are used — automatic mapping is a draft, not a
ground truth.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.ingest import parse_numbers  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402

CONCEPTS = [
    ("What was the bank's net profit?", ["net profit"]),
    ("What was the operating income?", ["operating income"]),
    ("What were the operating expenses?", ["operating expenses"]),
    ("What was the cost-to-income ratio?", ["cost-to-income"]),
    ("What was the net interest margin?", ["net interest margin"]),
    ("What was the non-performing loan ratio?", ["npl ratio", "non-performing"]),
    ("What was the provision coverage ratio?", ["allowance coverage", "provision coverage"]),
    ("What was the capital adequacy ratio?", ["capital adequacy ratio"]),
    ("What were the earnings per share?", ["earnings per share"]),
    ("What were the total assets?", ["total assets"]),
    ("What were the loans and advances to customers?", ["loans and advances to customers"]),
    ("What were the customer deposits?", ["deposits from customers"]),
    ("What was the impairment charge?", ["impairment losses"]),
]


def row_value(quote: str) -> float | None:
    for cell in quote.split(" | ")[1:]:
        numbers, _flag = parse_numbers(cell)
        if numbers:
            return numbers[0]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-page", type=int, default=40,
                    help="only look at early pages, where statements live")
    args = ap.parse_args()

    units = load_jsonl(Path(args.units))
    rows = [u for u in units if u.get("source") == "docling-row"
            and u.get("page", 0) <= args.max_page]

    out, missed = [], []
    print(f"{len(rows)} rows on pages 1-{args.max_page}\n")
    for i, (question, phrases) in enumerate(CONCEPTS, start=1):
        best, best_score = None, 0
        for unit in rows:
            label = unit["quote"].split(" | ")[0].lower().strip()
            score = 0
            for phrase in phrases:
                if label == phrase:
                    score = max(score, 3)
                elif label.startswith(phrase):
                    score = max(score, 2)
                elif phrase in label and not label.startswith(("average", "weighted", "return on")):
                    score = max(score, 1)
            if score <= best_score:
                continue
            value = row_value(unit["quote"])
            if value is not None and abs(value) > 0:
                best, best_score = (unit, value), score
        hit = best
        if hit is None:
            missed.append(question)
            print(f"  --  {question}")
            continue
        unit, value = hit
        out.append({"qid": f"N{i:02d}", "question": question,
                    "gold_value": value, "required_units": [unit["unit_id"]],
                    "doc": unit.get("doc", ""), "note": f"auto-mapped p{unit['page']}"})
        print(f"  ok  {value:>16,.2f}  p{unit['page']:>3}  {question}")

    Path(args.out).write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in out) + "\n")
    print(f"\n{len(out)} questions written to {args.out}; {len(missed)} unmapped")
    print("Review the mapping before using it: an automatic match is a draft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
