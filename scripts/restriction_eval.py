#!/usr/bin/env python3
"""What does the system do when the evidence is out of reach?

    python scripts/restriction_eval.py [--min-page 31]

A user with access to pages 31-277 sees the notes but not the primary statements
on pages 12-30. The correct behaviour is to refuse: the Group figures are not in
what they can see. Answering from a segment row in the notes instead — a real
number, correctly cited — is the failure this experiment looks for.

This is the permission case reduced to its load-bearing part: the evidence is
insufficient, and the system should say so.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, run, score_answer  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402

UNITS = Path("annotations/corpus/units.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-page", type=int, default=31,
                    help="lowest page the user may see")
    ap.add_argument("--questions", default="annotations/questions_blind.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    raw = attach_sections(load_jsonl(UNITS))
    questions = [q for q in load_jsonl(Path(args.questions)) if q.get("required_units")]
    from types import SimpleNamespace
    from finrag.agent_rag import value_matches

    # A page filter is not enough: the notes repeat every headline figure, so the
    # system can still answer legitimately. Insufficiency means the evidence is
    # genuinely outside the user's access, so every unit carrying the answer is
    # removed — and the correct behaviour is then to refuse.
    def visible_for(gold):
        return [u for u in raw
                if not any(value_matches(n, gold) for n in (u.get("numbers") or []))]

    all_units = [SimpleNamespace(**u) for u in raw]

    npz = sorted(Path("annotations/vectors").rglob("*.npz"),
                 key=lambda p: p.stat().st_mtime)
    index = UnitIndex.load(npz[-1]) if npz else None
    from sentence_transformers import CrossEncoder
    reranker = CrossEncoder("BAAI/bge-reranker-base")

    from concurrent.futures import ThreadPoolExecutor

    def ask(q):
        gold = q["gold_value"]
        units = [SimpleNamespace(**u) for u in visible_for(gold)]
        tools = Tools(units, vector_index=index, reranker=reranker)
        result = run(q["question"], DeepSeekClient(), tools, enforce=True)
        return {"qid": q["qid"], "question": q["question"], "gold": gold,
                "answer": result["answer"], "draft": result["draft"][:90],
                "status": result["verification"]["status"],
                "outcome": score_answer(result, gold)}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(ask, questions))

    counts = Counter(r["outcome"] for r in rows)
    lines = ["# Restriction experiment", "",
             "Condition: for each question, every unit carrying the gold value is "
             "removed — the evidence is outside the user's access.", "",
             "Correct behaviour: refuse. A correct figure from a segment row in the "
             "notes would be a *wrong* answer, not a successful one.", "",
             "| outcome | count |", "|---|---|"]
    for key in ("correct", "wrong", "rejected", "declined"):
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    lines += ["", "| qid | gold | what it did | outcome |", "|---|---|---|---|"]
    for r in rows:
        shown = (r["answer"] or r["draft"]).replace("|", "/")[:70]
        lines.append(f"| {r['qid']} | {r['gold']:,.0f} | {shown} | {r['outcome']} |")
    Path("RESTRICTION.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
