#!/usr/bin/env python3
"""Mark the annotated questions against the accepted evidence.

    python scripts/run_real_eval.py
    python scripts/run_real_eval.py --units path --questions path --out REAL_EVAL.md

Writes REAL_EVAL.md. If the files are empty it says so rather than printing a
table of zeros.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.real_eval import load_jsonl, mark, report, summarise  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", default="annotations/units.jsonl")
    ap.add_argument("--questions", default="annotations/questions.jsonl")
    ap.add_argument("--out", default="REAL_EVAL.md")
    args = ap.parse_args()

    unit_rows = load_jsonl(Path(args.units))
    questions = load_jsonl(Path(args.questions))

    lines = ["# Real-document evaluation", "",
             f"- accepted units: {len(unit_rows)}",
             f"- questions: {len(questions)}", ""]

    if not questions:
        lines += ["No questions yet. Use the app: accept a few units on a page, "
                  "then build a question from them in the second tab."]
    elif not unit_rows:
        lines += ["Questions exist but no units were accepted — nothing to cite."]
    else:
        units = {u["unit_id"]: u for u in unit_rows}
        rows = [mark(q, units) for q in questions]
        s = summarise(rows)
        lines += ["## Scores", "", "| measure | count |", "|---|---|"]
        for key in ("total", "correct", "wrong", "missing_evidence",
                    "no_value_parsed", "support_failures"):
            lines.append(f"| {key.replace('_', ' ')} | {s.get(key, 0)} |")
        lines += ["", "## Per question", "", report(rows), "",
                  "`missing evidence` means the question names a unit that is not "
                  "in the accepted set — the answer would have been unanswerable, "
                  "so it is counted separately from a wrong answer."]

    Path(args.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
