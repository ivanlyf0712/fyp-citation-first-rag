#!/usr/bin/env python3
"""Three retrieval arms over the whole document.

    python scripts/retrieval_arms.py

* **BM25** — words.
* **dense** — `bge-small-en-v1.5` over unit text, table rows with their header.
* **union** — top-5 from each, which is the best an agent that can call both
  tools could do without a reranker.

Reports, per question set, the rank of the unit that actually answers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag import metrics  # noqa: E402
from finrag.agent_rag import value_matches  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.retrieve import Bm25Index, Chunk  # noqa: E402
from finrag.vectors import UnitIndex, unit_contexts  # noqa: E402

UNITS = Path("annotations/corpus/units.jsonl")
import os  # noqa: E402


def value_hit(ranking_ids, units_by_id, gold, k):
    """Did the top-k contain a unit carrying the right number?

    The same statement appears in the primary statements and again in the notes.
    Requiring one exact unit id penalises a retriever for finding the equivalent
    row on the other page, so hits are also counted by value.
    """
    if gold is None:
        return 0.0
    for uid in ranking_ids[:k]:
        unit = units_by_id.get(uid)
        if unit and any(value_matches(n, gold) for n in unit["numbers"]):
            return 1.0
    return 0.0


def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal rank fusion, the weighting corpchat uses (equal weights here)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, uid in enumerate(ranking, start=1):
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda uid: -scores[uid])


class Row(dict):
    pass


def load_units(path: Path):
    return [Row(r) for r in load_jsonl(path)]


def main() -> int:
    units_path = Path(os.environ.get("UNITS_PATH", "annotations/corpus/units.jsonl"))
    if not units_path.exists():
        print("No unit corpus — run scripts/build_unit_corpus.py first.")
        return 1
    units = load_units(units_path)
    print(f"{len(units)} units")

    by_id = {u["unit_id"]: u for u in units}
    bm25 = Bm25Index()
    for u in units:
        bm25.add(Chunk(doc_id=u["unit_id"], page=u["page"],
                       text=f"{u['quote']} {u['channel']}"))
    bm25.finalize()

    # dense index over the same texts as the BM25 arm sees
    class U:
        def __init__(self, r):
            self.unit_id, self.doc, self.page = r["unit_id"], r["doc"], r["page"]
            self.quote, self.channel = r["quote"], r["channel"]
            self.numbers = tuple(r.get("numbers") or ())
            self.bbox = tuple(r["bbox"])
            self.source = r.get("source", "text-layer")

    dense_units = [U(r) for r in units]
    print("encoding…")
    dense = UnitIndex.build(dense_units)
    dense.save(Path("annotations/vectors/full"), source={"units": len(units)})

    sets = {
        "templated": load_jsonl(Path("annotations/questions.jsonl")),
        "paraphrase": load_jsonl(Path("annotations/questions_hard.jsonl")),
    }

    lines = ["# Retrieval arms over the whole document", "",
             f"{len(units)} units from 277 pages. Rank of the unit that answers.", ""]
    for set_name, questions in sets.items():
        questions = [q for q in questions if q.get("required_units")]
        if not questions:
            continue
        rows = []
        for q in questions:
            req = q["required_units"][0]
            bm = bm25.ranked_docs(q["question"], k=len(units))
            bm_rank = bm.index(req) + 1 if req in bm else None
            dn_rank = dense.rank_of(req, q["question"])
            dense_order = [uid for uid, _s in dense.search(q["question"], k=len(units))]
            fused = rrf([bm, dense_order])
            un_rank = fused.index(req) + 1 if req in fused else None
            rows.append({"qid": q["qid"], "question": q["question"],
                         "bm25": bm_rank, "dense": dn_rank, "union": un_rank,
                         "gold": q["gold_value"],
                         "bm25_hit5": value_hit(bm, by_id, q["gold_value"], 5),
                         "dense_hit5": value_hit(dense_order, by_id, q["gold_value"], 5),
                         "rrf_hit5": value_hit(fused, by_id, q["gold_value"], 5)})

        def r_at(key, k):
            return metrics.mean([1.0 if r[key] and r[key] <= k else 0.0 for r in rows])

        def mrr(key):
            return metrics.mean([1.0 / r[key] if r[key] else 0.0 for r in rows])

        lines += [f"## {set_name} ({len(rows)} questions)", "",
                  "| arm | exact R@1 | exact R@5 | value R@5 | MRR (exact) |",
                  "|---|---|---|---|---|"]
        for key in ("bm25", "dense", "union"):
            hit_key = {"bm25": "bm25_hit5", "dense": "dense_hit5",
                       "union": "rrf_hit5"}[key]
            lines.append(f"| {key} | {r_at(key,1):.2f} | {r_at(key,5):.2f} | "
                         f"{metrics.mean([r[hit_key] for r in rows]):.2f} | "
                         f"{mrr(key):.2f} |")
        lines += ["", "| qid | question | BM25 | dense | RRF |", "|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['qid']} | {r['question'][:55]} | {r['bm25'] or '—'} | "
                         f"{r['dense'] or '—'} | {r['union'] or '—'} |")
        lines.append("")

    Path("RETRIEVAL_ARMS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
