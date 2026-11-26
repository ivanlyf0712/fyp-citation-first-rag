#!/usr/bin/env python3
"""Baseline: the same agent, with verification switched off.

Isolates what the checks buy. Units, retrieval, tools and model are identical;
the only difference is that an answer is shown even when its numbers are not in
the quotes it cites. Every such answer is counted, because that is the thing the
checks exist to withhold.

    python scripts/baseline_no_check.py
"""
from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, run, score_answer, value_matches  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402

UNITS = Path("annotations/corpus/units.jsonl")
SETS = {
    "concept": Path("annotations/questions_blind.jsonl"),
    "paraphrase": Path("annotations/questions_paraphrase2.jsonl"),
}


def main() -> int:
    raw = attach_sections(load_jsonl(UNITS))
    units = [SimpleNamespace(**u) for u in raw]
    npz = sorted(Path("annotations/vectors").rglob("*.npz"),
                 key=lambda p: p.stat().st_mtime)
    index = UnitIndex.load(npz[-1]) if npz else None
    from sentence_transformers import CrossEncoder
    tools = Tools(units, vector_index=index,
                  reranker=CrossEncoder("BAAI/bge-reranker-base"))

    lines = ["# Baseline — same agent, verification off", "",
             "Identical units, retrieval, tools and model. The only change is that "
             "unsupported answers are shown rather than withheld.", ""]
    for name, path in SETS.items():
        questions = [q for q in load_jsonl(path) if q.get("gold_value")]

        def ask(q):
            result = run(q["question"], DeepSeekClient(), tools, enforce=False)
            return {"question": q["question"], "gold": q["gold_value"],
                    "answer": result["draft"], "citations": result["citations"],
                    "verdict": result["verification"]["status"],
                    "outcome": score_answer(result, q["gold_value"])}

        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(ask, questions))

        counts = Counter(r["outcome"] for r in rows)
        unsupported = sum(1 for r in rows if r["verdict"] == "rejected")
        lines += [f"## {name} ({len(rows)} questions)", "",
                  "| correct | wrong | declined | shown despite unsupported numbers |",
                  "|---|---|---|---|",
                  f"| {counts.get('correct',0)} | {counts.get('wrong',0)} | "
                  f"{counts.get('declined',0)} | **{unsupported}** |", ""]
        for r in rows:
            lines.append(f"| {r['question'][:55]} | {r['gold']:,.0f} | {r['outcome']} | "
                         f"{'unsupported' if r['verdict']=='rejected' else ''} |")
        lines.append("")

    Path("BASELINE_NO_CHECK.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
