#!/usr/bin/env python3
"""A two-minute command-line demo of the whole pipeline.

    export DEEPSEEK_API_KEY=...
    python scripts/demo_cli.py

Shows: the corpus, one answer with its citation, and the same question asked
with the evidence out of reach — which the system must refuse.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from finrag.agent_rag import Tools, run, value_matches  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402
from finrag.vectors import UnitIndex  # noqa: E402

UNITS = pathlib.Path("annotations/corpus/units.jsonl")
QUESTION = "What was the Group's net profit in 2024?"
GOLD = 5255815.0


def banner(text: str) -> None:
    print(f"\n\033[1m{text}\033[0m\n" + "─" * len(text))


def show(result: dict) -> None:
    verdict = result["verification"]
    print(f"  answer    : {result['answer'] or '(withheld)'}")
    print(f"  citations : {', '.join(result['citations']) or '—'}")
    print(f"  verdict   : {verdict['status']}")
    if verdict["failures"]:
        print(f"  reason    : {verdict['failures'][0]}")
    print(f"  tool calls: {result['tool_calls']}")


def main() -> int:
    if not UNITS.exists():
        print("No corpus. Run: python scripts/build_unit_corpus.py --pdf samples/<file>.pdf")
        return 1
    raw = attach_sections(load_jsonl(UNITS))
    units = [SimpleNamespace(**u) for u in raw]

    banner("1. The corpus")
    rows = sum(1 for u in units if u.source == "docling-row")
    print(f"  {len(units):,} units from {len({u.page for u in units})} pages "
          f"({rows:,} table rows)")
    print(f"  each unit = page, box, quote, value")

    npz = sorted(pathlib.Path("annotations/vectors").rglob("*.npz"),
                 key=lambda p: p.stat().st_mtime)
    index = UnitIndex.load(npz[-1]) if npz else None
    reranker = None
    try:
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder("BAAI/bge-reranker-base")
    except Exception:
        pass
    tools = Tools(units, vector_index=index, reranker=reranker)

    banner("2. Ask a question")
    print(f"  Q: {QUESTION}")
    result = run(QUESTION, DeepSeekClient(), tools)
    show(result)
    numbers = result["verification"]["numbers"]
    ok = any(value_matches(n, GOLD) for n in numbers)
    print(f"  correct   : {'yes' if ok else 'no'} (gold {GOLD:,.0f})")

    banner("3. Same question, evidence out of reach")
    visible = [u for u in units
               if not any(value_matches(n, GOLD) for n in u.numbers)]
    print(f"  removed every unit carrying {GOLD:,.0f} "
          f"({len(units) - len(visible)} units hidden)")
    result = run(QUESTION, DeepSeekClient(),
                 Tools(visible, vector_index=None, reranker=reranker))
    show(result)
    status = result["verification"]["status"]
    if status == "accepted":
        print("\n  Observed: it answered anyway, from a different row. That is the")
        print("  gap this project measures — the quote supports the number, but the")
        print("  number is not the figure that was asked for.")
    else:
        print("\n  Observed: it refused, as it should when the evidence is absent.")

    banner("4. Where the guarantee stops")
    print("  Verification proves a number is in the text it cites.")
    print("  It cannot tell 2024 from 2023, or the Group from a segment.")
    print("  See RESULTS.md, ENFORCEMENT.md and AUDIT.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
