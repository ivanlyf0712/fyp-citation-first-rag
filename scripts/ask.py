#!/usr/bin/env python3
"""Ask one question through the agent.

    python scripts/ask.py "What was the Group's net profit in 2024?"
    python scripts/ask.py "..." --stub        # offline demo, no key
    python scripts/ask.py "..." --semantic    # add the embedding tool

Writes one JSONL record to annotations/runs/ and prints the answer with its
citations and the verification verdict.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, run, score_answer  # noqa: E402
from finrag.ingest import load_cache, parse_pdf, save_cache  # noqa: E402
from finrag.llm import DeepSeekClient, StubClient  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402

PDF = Path("samples/bohai_bank_annual_2024.pdf")
CACHE = Path("annotations/cache")
RUNS = Path("annotations/runs")


def load_units(pages: list[int]) -> list:
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
    ap.add_argument("question")
    ap.add_argument("--pages", default="18")
    ap.add_argument("--stub", action="store_true",
                    help="offline: scripted replies, uses the top BM25 hit")
    ap.add_argument("--semantic", action="store_true",
                    help="add the embedding tool (needs annotations/vectors/)")
    args = ap.parse_args()

    pages = [int(p) for p in args.pages.split(",")]
    units = load_units(pages)

    vector_index = None
    if args.semantic:
        npz = sorted(Path("annotations/vectors").glob("*.npz"))
        if not npz:
            print("No embedding index — run scripts/vector_eval.py first.")
            return 1
        vector_index = UnitIndex.load(npz[-1])

    tools = Tools(units, vector_index=vector_index)

    if args.stub:
        top = tools.search_bm25(args.question, k=1)
        if not top:
            print("stub: no units match")
            return 1
        hit = top[0]
        value = hit["numbers"][0] if hit["numbers"] else 0
        client = StubClient(replies=[
            json.dumps({"tool": "search_bm25", "query": args.question, "k": 5}),
            json.dumps({"answer": f"The document states {value:,.0f}.",
                        "citations": [hit["unit_id"]]}),
        ])
        model = "stub"
    else:
        try:
            client = DeepSeekClient()
        except RuntimeError as exc:
            print(f"{exc}\n\nNothing was run. Add --stub for an offline plumbing check.")
            return 1
        model = client.model

    started = time.perf_counter()
    result = run(args.question, client, tools)
    elapsed = round((time.perf_counter() - started) * 1000, 1)

    print(f"\nQ: {args.question}")
    print(f"A: {result['answer'] or '(nothing)'}")
    print(f"citations: {result['citations']}")
    v = result["verification"]
    print(f"verdict: {v['status']}" + (f" — {v['failures']}" if v["failures"] else ""))
    print(f"tool calls: {result['tool_calls']} · {elapsed:.0f} ms · model {model}")

    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "model": model, "question": args.question,
              "answer": result["answer"], "citations": result["citations"],
              "verification": v, "trace": result["trace"],
              "tool_calls": result["tool_calls"], "latency_ms": elapsed,
              "outcome": score_answer(result, None)}
    with (RUNS / f"{stamp}.jsonl").open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return 0 if v["accepted"] or v["status"] == "declined" else 2


if __name__ == "__main__":
    raise SystemExit(main())
