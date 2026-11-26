#!/usr/bin/env python3
"""Second document, second language: BM25 vs multilingual dense vs fusion.

The Chinese filing parses into 10,052 units but BM25 alone retrieves at 0.20.
This adds `BAAI/bge-m3` (1024 dims, multilingual) and asks whether the method
travels.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import rrf_fuse  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.retrieve import Bm25Index, Chunk  # noqa: E402
from finrag.vectors import _model  # noqa: E402

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
    ("公司二零二五年的營業額是多少？", 751766),
    ("二零二五年公司賺了多少毛利？", 422593),
    ("二零二五年經營溢利是多少？", 241562),
    ("二零二五年除稅前利潤是多少？", 277249),
    ("二零二四年公司的營業額是多少？", 660257),
]


def main() -> int:
    units = load_jsonl(Path("annotations/corpus/tencent_units.jsonl"))
    rows = [u for u in units if u.get("source") == "docling-row"]
    ids = [u["unit_id"] for u in rows]
    by_id = {u["unit_id"]: u for u in rows}

    # the year is a column heading, not part of the row: index the header with
    # each row so "2025" can match at all
    headers: dict[tuple, str] = {}
    for u in sorted(rows, key=lambda r: (-r["bbox"][3], r["bbox"][0])):
        headers.setdefault((u["doc"], u["page"]), u["quote"])
    texts = {u["unit_id"]: f"{headers.get((u['doc'], u['page']), '')} :: {u['quote']}"
             for u in rows}

    bm25 = Bm25Index()
    for u in rows:
        bm25.add(Chunk(doc_id=u["unit_id"], page=u["page"],
                       text=texts[u["unit_id"]]))
    bm25.finalize()

    print(f"encoding {len(rows)} rows with bge-m3…", flush=True)
    model = _model("BAAI/bge-m3")
    matrix = model.encode([texts[u["unit_id"]] for u in rows], batch_size=16,
                          normalize_embeddings=True, convert_to_numpy=True,
                          show_progress_bar=False).astype(np.float32)
    qvecs = model.encode([q for q, _ in QUESTIONS], normalize_embeddings=True,
                         convert_to_numpy=True).astype(np.float32)

    def rank_of(ranking: list[str], gold: float) -> int | None:
        for pos, uid in enumerate(ranking, start=1):
            if any(abs(v - gold) < 0.5 for v in (by_id[uid].get("numbers") or [])):
                return pos
        return None

    stats = {"bm25": [], "dense": [], "rrf": []}
    for (question, gold), qv in zip(QUESTIONS, qvecs):
        bm = bm25.ranked_docs(question, k=len(rows))
        scores = matrix @ qv
        dense = [ids[i] for i in np.argsort(-scores)]
        fused = rrf_fuse([bm, dense])
        for name, ranking in (("bm25", bm), ("dense", dense), ("rrf", fused)):
            stats[name].append(rank_of(ranking, gold))

    def recall5(ranks):
        return sum(1 for r in ranks if r and r <= 5) / len(ranks)

    def mrr(ranks):
        return sum(1 / r for r in ranks if r) / len(ranks)

    lines = ["# Second document — Tencent 2025 (Chinese)", "",
             f"{len(rows)} table rows, {len(QUESTIONS)} Chinese questions, "
             "`BAAI/bge-m3` (1024 dims).", "",
             "| arm | Recall@5 | MRR |", "|---|---|---|"]
    for name in ("bm25", "dense", "rrf"):
        lines.append(f"| {name} | **{recall5(stats[name]):.2f}** | {mrr(stats[name]):.2f} |")
    lines += ["", "| question | gold | BM25 | dense | RRF |", "|---|---|---|---|---|"]
    for i, (question, gold) in enumerate(QUESTIONS):
        cell = lambda name: stats[name][i] or "—"
        lines.append(f"| {question} | {gold:,} | {cell('bm25')} | "
                     f"{cell('dense')} | {cell('rrf')} |")
    Path("TENCENT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
