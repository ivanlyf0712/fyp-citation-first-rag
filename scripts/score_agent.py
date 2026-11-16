#!/usr/bin/env python3
"""Run every annotated question through the agent and score it.

    python scripts/score_agent.py            # needs DEEPSEEK_API_KEY
    python scripts/score_agent.py --stub     # plumbing check only, meaningless scores

A stub run writes AGENT_RESULTS.stub.md and says so at the top: the stub answers
with the top BM25 hit, so its scores measure the plumbing, not the model.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, run, score_answer  # noqa: E402
from finrag.ingest import load_cache, parse_pdf, save_cache  # noqa: E402
from finrag.llm import DeepSeekClient, StubClient  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402

PDF = Path("samples/bohai_bank_annual_2024.pdf")
CACHE = Path("annotations/cache")


def units_for(pages: list[int]) -> list:
    units = []
    for page in pages:
        cached = load_cache(CACHE, PDF, page, page)
        if cached is None:
            cached = parse_pdf(PDF, start=page, end=page)
            save_cache(CACHE, PDF, cached, page, page)
        units.extend(cached)
    return units


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="18")
    ap.add_argument("--stub", action="store_true")
    ap.add_argument("--questions", default="annotations/questions.jsonl")
    ap.add_argument("--out", default=None)
    ap.add_argument("--units", default=None,
                    help="JSONL unit corpus; otherwise pages are parsed/cached")
    ap.add_argument("--model", default=None, help="override the chat model")
    ap.add_argument("--workers", type=int, default=4,
                    help="questions run concurrently; independent by construction")
    ap.add_argument("--sections", action="store_true",
                    help="attach page-heading context to every unit")
    ap.add_argument("--rerank", action="store_true",
                    help="give the expansion tool a cross-encoder reranker")
    ap.add_argument("--semantic", action="store_true",
                    help="give the agent the embedding tool as well as BM25")
    args = ap.parse_args()

    questions = load_jsonl(Path(args.questions))
    if not questions:
        print("No questions annotated.")
        return 1
    if args.units:
        raw = load_jsonl(Path(args.units))
        if args.sections:
            raw = attach_sections(raw)
        units = [SimpleNamespace(**r) for r in raw]
    else:
        units = units_for([int(p) for p in args.pages.split(",")])
        if args.sections:
            print("--sections needs --units; ignored for parsed pages")
    vector_index = None
    if args.semantic:
        npz = sorted(Path("annotations/vectors").rglob("*.npz"),
                     key=lambda p: p.stat().st_mtime)
        if not npz:
            print("No embedding index — run scripts/vector_eval.py first.")
            return 1
        vector_index = UnitIndex.load(npz[-1])
    reranker = None
    if args.rerank:
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder("BAAI/bge-reranker-base")
    tools = Tools(units, vector_index=vector_index, reranker=reranker)

    def ask_one(q: dict) -> dict:
        if args.stub:
            top = tools.search_bm25(q["question"], k=1)
            if not top:
                return {"qid": q["qid"], "gold": q["gold_value"], "answer": "",
                        "citations": [], "verdict": "no_hit", "cited_required": False,
                        "outcome": "no_hit"}
            hit = top[0]
            value = hit["numbers"][0] if hit["numbers"] else 0
            client = StubClient(replies=[
                json.dumps({"tool": "search_bm25", "query": q["question"]}),
                json.dumps({"answer": f"The document states {value}.",
                            "citations": [hit["unit_id"]]}),
            ])
        else:
            client = DeepSeekClient(model=args.model) if args.model else DeepSeekClient()

        result = run(q["question"], client, tools)
        result["_units"] = tools._by_id
        required = set(q.get("required_units") or ())
        return {"qid": q["qid"], "gold": q["gold_value"],
                "answer": result["answer"], "citations": result["citations"],
                "verdict": result["verification"]["status"],
                "cited_required": bool(required) and required <= set(result["citations"]),
                "outcome": score_answer(result, q["gold_value"])}

    workers = 1 if args.stub else max(1, args.workers)
    if workers == 1:
        rows = [ask_one(q) for q in questions]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(ask_one, questions))

    counts = Counter(r["outcome"] for r in rows)
    name = args.out or ("AGENT_RESULTS.stub.md" if args.stub else "AGENT_RESULTS.md")
    lines = ["# Agent results" + (" (STUB — plumbing only)" if args.stub else ""), ""]
    if args.stub:
        lines += ["> **These scores are meaningless.** The stub answers with the "
                  "top BM25 hit and no model is involved. This file exists to "
                  "prove the loop, enforcement and logging run end to end.", ""]
    cited = sum(1 for r in rows if r.get("cited_required"))
    lines += [f"- questions: {len(rows)}", f"- units available: {len(units)}",
              f"- cited the required unit: {cited}/{len(rows)}", "",
              "| outcome | count |", "|---|---|"]
    for key in ("correct", "wrong", "rejected", "declined", "no_hit"):
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    lines += ["", "| qid | gold | answer | verdict | cited required | outcome |",
              "|---|---|---|---|---|---|"]
    for r in rows:
        answer = (r["answer"] or "")[:70].replace("|", "/")
        lines.append(f"| {r['qid']} | {r['gold']:,.0f} | {answer} | "
                     f"{r.get('verdict', '—')} | "
                     f"{'yes' if r.get('cited_required') else 'no'} | {r['outcome']} |")
    Path(name).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
