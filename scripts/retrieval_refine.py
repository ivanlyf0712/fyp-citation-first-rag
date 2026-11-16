#!/usr/bin/env python3
"""Four retrieval arms, one question set, one table.

    python scripts/retrieval_refine.py [--arms a0,a1,a2,a3,a4]

A0 baseline is BM25 + dense + RRF over the full unit text. Each arm changes one
thing. Nothing is adopted unless it clears the bar in docs/RETRIEVAL_SPEC.md; a
failing arm is still written to the report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from finrag import metrics  # noqa: E402
from finrag.agent_rag import expand_query, rrf_fuse, value_matches  # noqa: E402
from finrag.ingest import parse_numbers  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.retrieve import Bm25Index, Chunk  # noqa: E402
from finrag.vectors import _model  # noqa: E402

UNITS = Path("annotations/corpus/units.jsonl")
EXPANSIONS = Path("annotations/expansions.json")
MODEL = "BAAI/bge-small-en-v1.5"


def load_rows():
    return load_jsonl(UNITS)


def headers_for(rows):
    out = {}
    for u in sorted(rows, key=lambda r: (-r["bbox"][3], r["bbox"][0])):
        if u.get("source") == "docling-row":
            out.setdefault((u["doc"], u["page"]), u["quote"])
    return out


def label_of(quote: str) -> str:
    return quote.split(" | ")[0].strip()


def value_of(quote: str):
    cells = quote.split(" | ")
    for cell in cells[1:]:
        nums, _ = parse_numbers(cell)
        if nums:
            return nums[0]
    nums, _ = parse_numbers(cells[0])
    return nums[0] if nums else None


class Dense:
    def __init__(self, texts: list[str]):
        self.texts = texts
        self.matrix = _model(MODEL).encode(
            texts, batch_size=64, convert_to_numpy=True,
            normalize_embeddings=True, show_progress_bar=False).astype(np.float32)

    def rank(self, query: str) -> list[int]:
        q = _model(MODEL).encode([query], normalize_embeddings=True,
                                 convert_to_numpy=True)[0].astype(np.float32)
        return list(np.argsort(-(self.matrix @ q)))


def build_index(texts: list[str]) -> Bm25Index:
    index = Bm25Index()
    for i, text in enumerate(texts):
        index.add(Chunk(doc_id=str(i), page=0, text=text))
    index.finalize()
    return index


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="a0,a1,a2,a3,a4")
    ap.add_argument("--out", default="RETRIEVAL_REFINEMENT.md")
    args = ap.parse_args()
    arms = [a.strip() for a in args.arms.split(",")]

    rows = load_rows()
    ids = [r["unit_id"] for r in rows]
    headers = headers_for(rows)
    full_texts = [f"{r['quote']} {r['channel']}" for r in rows]
    label_texts = [f"{headers.get((r['doc'], r['page']), '')} :: {label_of(r['quote'])}"
                   if r.get("source") == "docling-row" else r["quote"] for r in rows]

    print(f"{len(rows)} units; encoding two representations…")
    bm25_full, bm25_label = build_index(full_texts), build_index(label_texts)
    dense_full, dense_label = Dense(full_texts), Dense(label_texts)

    sets = {"label-derived": Path("annotations/questions.jsonl"),
            "paraphrase": Path("annotations/questions_hard.jsonl")}
    questions = {name: [q for q in load_jsonl(path) if q.get("required_units")]
                 for name, path in sets.items()}

    # expansion rewrites, cached: an LLM call per question, once
    cache = json.loads(EXPANSIONS.read_text()) if EXPANSIONS.exists() else {}
    need = [q["question"] for qs in questions.values() for q in qs]
    if any(q not in cache for q in need) and "a2" in arms:
        from finrag.llm import DeepSeekClient
        client = DeepSeekClient()
        for q in need:
            if q not in cache:
                cache[q] = expand_query(client, q)
        EXPANSIONS.write_text(json.dumps(cache, indent=1))

    reranker = None
    if any(a in arms for a in ("a4", "a5", "a6")):
        try:
            from sentence_transformers import CrossEncoder
            print("loading reranker…", flush=True)
            reranker = CrossEncoder("BAAI/bge-reranker-base")
        except Exception as exc:                     # noqa: BLE001
            print(f"reranker unavailable, skipping A4: {exc}")
            arms = [a for a in arms if a not in ("a4", "a5", "a6")]

    def bm_rank(index, query):
        return index.ranked_docs(query, k=len(ids))

    def fusable(*rankings):
        lists = [[ids[int(i)] for i in r] for r in rankings if r]
        return rrf_fuse(lists)

    def rank_a0(q):
        return fusable(bm_rank(bm25_full, q), dense_full.rank(q))

    def rank_a1(q):
        return fusable(bm_rank(bm25_label, q), dense_label.rank(q))

    def rank_a2(q):
        variants = cache.get(q, [q])
        rankings = []
        for v in variants:
            rankings.append(bm_rank(bm25_full, v))
            rankings.append(dense_full.rank(v))
        return fusable(*rankings)

    def rank_a3(q):
        fused = rank_a0(q)
        kept, seen = [], {}
        for uid in fused:
            row = by_id[uid]
            value = value_of(row["quote"])
            key = (label_of(row["quote"]).lower(),
                   round(abs(value), 2) if value is not None else None)
            if key in seen:
                continue
            seen[key] = uid
            kept.append(uid)
        return kept

    def rerank(query, ranking):
        pairs = [(query, full_texts[ids.index(uid)]) for uid in ranking]
        scores = reranker.predict(pairs)
        return [ranking[i] for i in np.argsort(-np.asarray(scores))]

    def rank_a5(q):
        return rerank(q, rank_a2(q)[:30])

    def rank_a6(q):
        return rerank(q, rank_a1(q)[:30])

    def rank_a4(q):
        fused = rank_a0(q)[:30]
        pairs = [(q, full_texts[ids.index(uid)]) for uid in fused]
        scores = reranker.predict(pairs)
        order = np.argsort(-np.asarray(scores))
        return [fused[i] for i in order]

    by_id = {r["unit_id"]: r for r in rows}
    arms_fn = {"a0": rank_a0, "a1": rank_a1, "a2": rank_a2,
               "a3": rank_a3, "a4": rank_a4, "a5": rank_a5, "a6": rank_a6}

    def value_hit(ranking, gold, k=5):
        for uid in ranking[:k]:
            if any(value_matches(n, gold) for n in by_id[uid].get("numbers") or []):
                return 1.0
        return 0.0

    results = {}
    for arm in arms:
        fn = arms_fn[arm]
        for set_name, qs in questions.items():
            hits, ranks = [], []
            for q in qs:
                ranking = fn(q["question"])
                gold = q.get("gold_value")
                hits.append(value_hit(ranking, gold))
                req = q["required_units"][0]
                ranks.append(ranking.index(req) + 1 if req in ranking else None)
            results[(arm, set_name)] = {
                "hit5": metrics.mean(hits),
                "r1": metrics.mean([1.0 if r and r <= 1 else 0.0 for r in ranks]),
                "mrr": metrics.mean([1.0 / r if r else 0.0 for r in ranks]),
            }
        print(arm, "done", flush=True)

    lines = ["# Retrieval refinement — four arms", "",
             f"{len(rows)} units, {len(questions['label-derived'])} label-derived "
             f"+ {len(questions['paraphrase'])} paraphrase questions.", "",
             "| arm | question set | value-R@5 | exact R@1 | MRR |",
             "|---|---|---|---|---|"]
    names = {"a0": "A0 baseline", "a1": "A1 label representation",
             "a2": "A2 expansion", "a3": "A3 dedupe", "a4": "A4 reranker",
             "a5": "A2+A4 expansion then rerank", "a6": "A1+A4 label then rerank"}
    for arm in arms:
        for set_name in questions:
            r = results[(arm, set_name)]
            lines.append(f"| {names[arm]} | {set_name} | **{r['hit5']:.2f}** | "
                         f"{r['r1']:.2f} | {r['mrr']:.2f} |")
    base_par = results.get(("a0", "paraphrase"), {}).get("hit5", 0.20)
    base_lab = results.get(("a0", "label-derived"), {}).get("hit5", 0.74)
    lines += ["", f"Bar: paraphrase +0.10 over {base_par:.2f}, label-derived "
                  f">= {base_lab - 0.03:.2f}.", ""]
    Path(args.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
