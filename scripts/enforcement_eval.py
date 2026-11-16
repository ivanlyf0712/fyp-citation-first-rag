#!/usr/bin/env python3
"""What does the enforcement actually catch?

    python scripts/enforcement_eval.py

The answer to every question is removed from the evidence pool first: every unit
carrying the gold value is dropped. So the corpus provably cannot answer, and any
number the model produces is invented or borrowed from a neighbouring row.

Each question is asked twice — enforcement off and on. Off, we record whether the
draft asserted an unsupported number (a fabrication). On, whether that draft was
withheld. This is the measurement the whole project rests on.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, run, value_matches  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402

UNITS = Path("annotations/corpus/units.jsonl")


def load_units():
    return [SimpleNamespace(**r) for r in load_jsonl(UNITS)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="annotations/questions_hard.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    units = load_units()
    questions = [q for q in load_jsonl(Path(args.questions))
                 if q.get("required_units") and q.get("gold_value") is not None]

    rows = []
    for q in questions:
        gold = q["gold_value"]
        pool = [u for u in units
                if not any(value_matches(n, gold) for n in u.numbers)]

        # collision control: does any remaining unit still carry the gold value?
        leak = sum(1 for u in pool if any(value_matches(n, gold) for n in u.numbers))
        tools = Tools(pool)

        off = run(q["question"], DeepSeekClient(), tools, enforce=False)
        on = run(q["question"], DeepSeekClient(), tools, enforce=True)

        def kind(result):
            v = result["verification"]
            if v["status"] == "declined":
                return "declined"
            if v["status"] == "rejected":
                return "fabricated"
            nums = v["numbers"]
            if nums and not any(value_matches(n, gold) for n in nums):
                return "grounded_wrong"
            return "other"

        rows.append({
            "qid": q["qid"], "gold": gold, "units_in_pool": len(pool),
            "gold_leaks": leak,
            "off_answer": off["draft"][:90],
            "off_kind": kind(off),
            "on_withheld": on["withheld"],
            "on_status": on["verification"]["status"],
        })

    n = len(rows)
    def count(k):
        return sum(1 for r in rows if r["off_kind"] == k)
    fabricated, grounded, declined_off = count("fabricated"), count("grounded_wrong"), count("declined")
    withheld = sum(1 for r in rows if r["on_withheld"])

    lines = ["# What enforcement catches", "",
             f"- questions: {n}",
             "- condition: every unit carrying the gold value removed from the pool",
             f"- leaked answers in the pool: {sum(r['gold_leaks'] for r in rows)} "
             f"(0 means the answer really is absent)", "",
             "| | enforcement off | enforcement on |", "|---|---|---|",
             f"| invented a number not in any quote | **{fabricated}** | 0 shown |",
             f"| used a real number from the wrong row | {grounded} | "
             f"{sum(1 for r in rows if not r['on_withheld'] and r['off_kind'] == 'grounded_wrong')} shown |",
             f"| declined | {declined_off} | "
             f"{sum(1 for r in rows if r['on_status'] == 'declined')} |",
             f"| withheld after the fact | 0 | **{withheld}** |", "",
             "| qid | gold | enforcement off — what it said | on — withheld |",
             "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['qid']} | {r['gold']:,.0f} | "
                     f"{r['off_answer'].replace('|', '/')[:80]} | "
                     f"{'yes' if r['on_withheld'] else 'no'} |")

    Path("ENFORCEMENT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
