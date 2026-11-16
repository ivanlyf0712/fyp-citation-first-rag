#!/usr/bin/env python3
"""Does the pipeline survive a second, Chinese document?

bge-small is English-only, so this run uses character-level BM25 only. It
answers a narrower question than the Bohai evaluation: can the parser's units be
searched and cited in Chinese at all, before any multilingual encoder is added.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.retrieve import Bm25Index, Chunk  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")


def spaced(text: str) -> str:
    """Put spaces around CJK characters so the word tokenizer sees characters."""
    return CJK.sub(lambda m: f" {m.group(0)} ", text)


QUESTIONS = [
    ("二零二五年的收入是多少？", 751766),
    ("二零二五年的毛利是多少？", 422593),
    ("二零二五年的經營盈利是多少？", 241562),
    ("二零二五年的除稅前盈利是多少？", 277249),
    ("二零二四年的收入是多少？", 660257),
    ("二零二四年的毛利是多少？", 349246),
    ("二零二三年的收入是多少？", 609015),
    ("二零二三年的毛利是多少？", 293109),
    ("二零二二年的經營盈利是多少？", 110827),
    ("二零二一年的收入是多少？", 560118),
]


def main() -> int:
    units = load_jsonl(Path("annotations/corpus/tencent_units.jsonl"))
    rows = [u for u in units if u.get("source") == "docling-row"]
    index = Bm25Index()
    for unit in rows:
        index.add(Chunk(doc_id=unit["unit_id"], page=unit["page"],
                        text=unit["quote"]))
    index.finalize()

    hits = 0
    lines = ["# Second document — Tencent 2025 (Chinese)", "",
             f"{len(rows)} table rows, character-level BM25 (no encoder: bge-small is English-only).", "",
             "| question | gold | rank of a row containing it |", "|---|---|---|"]
    for question, gold in QUESTIONS:
        ranked = index.ranked_docs(question, k=len(rows))
        rank = None
        for position, uid in enumerate(ranked, start=1):
            unit = next(u for u in rows if u["unit_id"] == uid)
            if gold in (unit.get("numbers") or []):
                rank = position
                break
        hits += 1 if rank and rank <= 5 else 0
        lines.append(f"| {question} | {gold:,} | {rank or '—'} |")
    lines += ["", f"Recall@5: **{hits}/{len(QUESTIONS)}** = {hits/len(QUESTIONS):.2f}"]
    Path("TENCENT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
