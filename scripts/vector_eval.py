#!/usr/bin/env python3
"""Words vs meaning: can each arm find the unit a question needs?

    python scripts/vector_eval.py [--pages 18,24]

Embeds every parsed unit with `bge-small-en-v1.5` (table rows get their header
row prepended), then for each annotated question finds the rank of the required
unit under:

* **BM25** over the same unit texts;
* **cosine** in the embedding index.

Reports rank, Recall@1/@5 and MRR for both. With one question this is a smoke
test; the table grows as questions are added.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag import metrics  # noqa: E402
from finrag.ingest import load_cache, parse_pdf, save_cache  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.retrieve import Bm25Index, Chunk  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402

PDF = Path("samples/bohai_bank_annual_2024.pdf")
CACHE = Path("annotations/cache")
VECTORS = Path("annotations/vectors")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="18,24")
    args = ap.parse_args()

    units = []
    for page in [int(p) for p in args.pages.split(",")]:
        cached = load_cache(CACHE, PDF, page, page)
        if cached is None:
            cached = parse_pdf(PDF, start=page, end=page)
            save_cache(CACHE, PDF, cached, page, page)
        units.extend(cached)
    print(f"{len(units)} units from pages {args.pages}")

    questions = load_jsonl(Path("annotations/questions.jsonl"))
    if not questions:
        print("No questions annotated yet — annotate a unit and a question first.")
        return 1

    print("building embeddings…")
    index = UnitIndex.build(units)
    npz, manifest = index.save(VECTORS, source={"pdf": str(PDF), "pages": args.pages})
    print(f"saved {npz.name} ({index.vectors.shape})")

    bm25 = Bm25Index()
    for unit in units:
        bm25.add(Chunk(doc_id=unit.unit_id, page=unit.page, text=unit.quote))
    bm25.finalize()

    rows = []
    for q in questions:
        required = (q.get("required_units") or [None])[0]
        if required is None:
            continue
        emb_rank = index.rank_of(required, q["question"])
        order = bm25.ranked_docs(q["question"], k=len(units))
        bm_rank = order.index(required) + 1 if required in order else None
        rows.append({"qid": q.get("qid"), "question": q["question"],
                     "emb": emb_rank, "bm25": bm_rank})

    def recall(rank, k):
        return 1.0 if rank and rank <= k else 0.0

    lines = ["# Words vs meaning", "",
             f"{len(units)} units, {len(rows)} questions, "
             f"`{index.model_id}` ({index.vectors.shape[1]} dims).", "",
             "| qid | question | BM25 rank | embedding rank |",
             "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['qid']} | {r['question'][:60]} | {r['bm25'] or '—'} | "
                     f"{r['emb'] or '—'} |")

    lines += ["", "| arm | Recall@1 | Recall@5 | MRR |", "|---|---|---|---|",
              f"| BM25 | {metrics.mean([recall(r['bm25'], 1) for r in rows]):.2f} | "
              f"{metrics.mean([recall(r['bm25'], 5) for r in rows]):.2f} | "
              f"{metrics.mean([1 / r['bm25'] if r['bm25'] else 0 for r in rows]):.2f} |",
              f"| embeddings | {metrics.mean([recall(r['emb'], 1) for r in rows]):.2f} | "
              f"{metrics.mean([recall(r['emb'], 5) for r in rows]):.2f} | "
              f"{metrics.mean([1 / r['emb'] if r['emb'] else 0 for r in rows]):.2f} |",
              "", ("smoke test — too few questions to claim a difference."
                   if len(rows) < 30 else
                   f"{len(rows)} questions, one document. Enough to see a gap, "
                   "not enough to call it stable across filings.")]

    Path("VECTORS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
