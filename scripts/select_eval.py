#!/usr/bin/env python3
"""Select-then-extract vs the agent, on the same questions."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, value_matches  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402
from finrag.select import select_and_extract  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="annotations/questions_paraphrase2.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    raw = attach_sections(load_jsonl(Path("annotations/corpus/units.jsonl")))
    units = [SimpleNamespace(**u) for u in raw]
    npz = sorted(Path("annotations/vectors").rglob("*.npz"),
                 key=lambda p: p.stat().st_mtime)[-1]
    from sentence_transformers import CrossEncoder
    tools = Tools(units, vector_index=UnitIndex.load(npz),
                  reranker=CrossEncoder("BAAI/bge-reranker-base"))

    questions = [q for q in load_jsonl(Path(args.questions)) if q.get("required_units")]

    def ask(q):
        client = DeepSeekClient(model=args.model) if args.model else DeepSeekClient()
        result = select_and_extract(q["question"], client, tools)
        numbers = result["verification"]["numbers"]
        if result["verification"]["status"] == "declined" or not numbers:
            outcome = "declined"
        elif any(value_matches(n, q["gold_value"]) for n in numbers):
            outcome = "correct"
        else:
            outcome = "wrong"
        return {"qid": q["qid"], "gold": q["gold_value"], "outcome": outcome,
                "answer": result["answer"][:70], "candidates": result.get("candidates", 0)}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(ask, questions))

    counts = Counter(r["outcome"] for r in rows)
    lines = ["# Select then extract", "",
             f"{len(rows)} questions, label chosen by the model, number read by code.", "",
             "| outcome | count |", "|---|---|"]
    for key in ("correct", "wrong", "declined"):
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    lines += ["", "| qid | gold | outcome | answer |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['qid']} | {r['gold']:,.0f} | {r['outcome']} | {r['answer']} |")
    Path("SELECT_EXTRACT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
