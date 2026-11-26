#!/usr/bin/env python3
"""LLM-as-judge: a second model grades answers the deterministic scorer graded.

Two questions:
  1. does the judge agree with exact-number scoring on correctness?
  2. does it agree that an answer is faithful to its citations?

Agreement is reported as raw percentage and Cohen's kappa. The judge is not the
ground truth — it is an independent second opinion, and disagreements are the
interesting part.

    python scripts/judge_eval.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, run, score_answer  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402

SETS = {"concept": "annotations/questions_blind.jsonl",
        "paraphrase": "annotations/questions_paraphrase2.jsonl"}
PROMPT = """You are grading an answer about a financial report.

Question: {question}
Reference value: {gold}
Answer: {answer}
Quotes the answer cites:
{quotes}

Return ONLY JSON:
{{"correct": true/false, "faithful": true/false, "reason": "<one line>"}}
"correct" means the answer's figure matches the reference value (allow rounding
and unit scaling). "faithful" means every number in the answer appears in the
quotes above."""


def judge(question, gold, answer, quotes) -> dict:
    key = os.environ["LITELLM_API_KEY"]
    base = os.environ["LITELLM_BASE_URL"].rstrip("/")
    response = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "deepseek-chat", "temperature": 0, "max_tokens": 300,
              "messages": [{"role": "user", "content": PROMPT.format(
                  question=question, gold=f"{gold:,.2f}", answer=answer or "(none)",
                  quotes=quotes)}]},
        timeout=90)
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1])
    except Exception:                                    # noqa: BLE001
        return {}


def kappa(pairs) -> float:
    if not pairs:
        return 0.0
    n = len(pairs)
    agree = sum(1 for a, b in pairs if a == b) / n
    pa = sum(1 for a, _ in pairs if a) / n
    pb = sum(1 for _, b in pairs if b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return 0.0 if expected == 1 else (agree - expected) / (1 - expected)


def main() -> int:
    raw = attach_sections(load_jsonl(Path("annotations/corpus/units.jsonl")))
    units = [SimpleNamespace(**u) for u in raw]
    npz = sorted(Path("annotations/vectors").rglob("*.npz"), key=lambda p: p.stat().st_mtime)
    from sentence_transformers import CrossEncoder
    tools = Tools(units, vector_index=UnitIndex.load(npz[-1]) if npz else None,
                  reranker=CrossEncoder("BAAI/bge-reranker-base"))

    lines = ["# LLM as judge", ""]
    for name, path in SETS.items():
        questions = [q for q in load_jsonl(Path(path)) if q.get("gold_value")]

        def one(q):
            result = run(q["question"], DeepSeekClient(), tools)
            quotes = "\n".join(
                f"[{uid}] {tools._by_id[uid].quote[:300]}"
                for uid in result["citations"] if uid in tools._by_id) or "(none)"
            verdict = judge(q["question"], q["gold_value"],
                            result["answer"] or result["draft"], quotes)
            deterministic = score_answer(result, q["gold_value"]) == "correct"
            return {"qid": q["qid"], "deterministic": deterministic,
                    "judge_correct": bool(verdict.get("correct")),
                    "judge_faithful": bool(verdict.get("faithful")),
                    "reason": str(verdict.get("reason", ""))[:80]}

        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(one, questions))

        pairs = [(r["deterministic"], r["judge_correct"]) for r in rows]
        agree = sum(1 for a, b in pairs if a == b) / len(pairs)
        faithful = sum(1 for r in rows if r["judge_faithful"])
        lines += [f"## {name} ({len(rows)} questions)", "",
                  f"- agreement on correctness: **{agree:.2f}** (kappa {kappa(pairs):.2f})",
                  f"- judge says faithful to citations: {faithful}/{len(rows)}",
                  f"- deterministic correct: {sum(1 for r in rows if r['deterministic'])}",
                  f"- judge correct: {sum(1 for r in rows if r['judge_correct'])}", ""]
        for r in rows:
            if r["deterministic"] != r["judge_correct"]:
                lines.append(f"| {r['qid']} | deterministic {r['deterministic']} | "
                             f"judge {r['judge_correct']} | {r['reason']} |")
        lines.append("")

    Path("JUDGE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
