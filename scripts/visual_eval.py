#!/usr/bin/env python3
"""Text-to-page-image retrieval, scored the same way as BM25.

    python scripts/visual_eval.py

Builds a CLIP ViT-B/32 index over every page, then scores it against the gold
evidence of each probe with Recall@10, nDCG@10 and MRR — the same metrics and
the same probes as the lexical arm, so the two numbers are comparable.

The first run downloads the model (~600 MB) and encodes 121 pages; the
embeddings are cached in build/clip_pages.npz.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag import metrics  # noqa: E402
from finrag.documents import load_corpus  # noqa: E402
from finrag.probes import build_probes  # noqa: E402
from finrag.retrieve import Bm25Index  # noqa: E402
from finrag.visual import ClipIndex, render_pages  # noqa: E402


def score(ranked_fn) -> dict:
    rows = []
    for probe in PROBES:
        if probe.gold is None:
            continue
        ranked = ranked_fn(probe)
        rows.append({
            "type": probe.type,
            "recall": metrics.recall_at_k(ranked, EVIDENCE[probe.qid], 10),
            "ndcg": metrics.ndcg_at_k(ranked, EVIDENCE[probe.qid], 10),
            "mrr": metrics.reciprocal_rank(ranked, EVIDENCE[probe.qid]),
        })
    out = {}
    for qtype in sorted({r["type"] for r in rows}):
        sub = [r for r in rows if r["type"] == qtype]
        out[qtype] = {"n": len(sub),
                      "recall": metrics.mean([r["recall"] for r in sub]),
                      "ndcg": metrics.mean([r["ndcg"] for r in sub]),
                      "mrr": metrics.mean([r["mrr"] for r in sub])}
    out["all"] = {"n": len(rows),
                  "recall": metrics.mean([r["recall"] for r in rows]),
                  "ndcg": metrics.mean([r["ndcg"] for r in rows]),
                  "mrr": metrics.mean([r["mrr"] for r in rows])}
    return out


corpus = load_corpus(Path("build"))
PROBES = build_probes(corpus)

# gold pages per probe: for a cell, its memo; for a total, the memos plus the
# group statement
EVIDENCE: dict[str, set[str]] = {}
for probe in PROBES:
    docs: set[str] = set()
    for key, fact in corpus.facts.items():
        if key.entity != probe.counterparty:
            continue
        if probe.type == "cell" and key.scope != probe.scope:
            continue
        docs |= {o.doc_id for o in fact.observations}
    EVIDENCE[probe.qid] = docs


def main() -> int:
    cache = Path("build/clip_pages.npz")
    index = ClipIndex()
    if cache.exists():
        index.load(cache)
        print(f"loaded cached embeddings ({len(index.keys)} pages)")
    else:
        pages = render_pages(corpus, Path("build"))
        print(f"encoding {len(pages)} pages on {index.device}…")
        index.build(pages)
        index.save(cache)
        print(f"cached to {cache}")

    lexical = Bm25Index.from_corpus(corpus, Path("build"))

    visual_scores = score(lambda p: index.ranked_docs(p.text, k=10))
    lexical_scores = score(lambda p: lexical.ranked_docs(p.text, k=10))

    lines = ["# Visual retrieval — CLIP over page images", "",
             "CLIP ViT-B/32, one vector per page at 224 px, cosine similarity "
             "against a text query. Same probes, same gold evidence, same k = 10 "
             "as the lexical arm.", "",
             "| arm | probe type | n | Recall@10 | nDCG@10 | MRR |",
             "|---|---|---|---|---|---|"]
    for name, scores in (("BM25 (text)", lexical_scores), ("CLIP (image)", visual_scores)):
        for qtype in ("cell", "total", "all"):
            m = scores[qtype]
            lines.append(f"| {name} | {qtype} | {m['n']} | {m['recall']:.3f} | "
                         f"{m['ndcg']:.3f} | {m['mrr']:.3f} |")

    lines += ["", "## Reading", "",
              "CLIP embeds the whole page into a single vector, so it can match "
              "the *kind* of page — a credit memo, a chart — but not the specific "
              "figure inside it. On a corpus where every page looks alike and the "
              "answer turns on one number, that is the wrong granularity, and the "
              "numbers above should be read as the cost of it.", "",
              "This is the gap ColPali was built to close: late interaction over "
              "page patches preserves the local detail that a single page vector "
              "averages away. Adding it, and comparing, is the next rung."]

    Path("VISUAL.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
