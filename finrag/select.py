"""Select then extract: the model picks a label, the code reads the number.

FinQA and Program-of-Thoughts both separate *which cell* from *what is in it*.
The reason is visible in our own failures: when one call both chooses and reads,
the model writes a fluent sentence quoting a neighbouring row's figure, and no
string check can tell.

Here the model sees ten labels and no numbers, answers with one index, and the
number is lifted from the chosen row by code. A mis-selection becomes visible and
countable; a mis-transcription becomes impossible.
"""

from __future__ import annotations

import re

from .agent_rag import Tools, verify_answer
from .ingest import parse_numbers
from .llm import parse_turn

PROMPT = """You are answering a question about a financial report.

Question: {question}

Candidate line items (labels only, no numbers):
{choices}

Which single line item answers the question? Reply with JSON only:
{{"choice": <number>, "reason": "<short>"}}
If none of them answers it, reply {{"choice": 0, "reason": "..."}}."""


def _value_of(quote: str) -> float | None:
    cells = quote.split(" | ")
    for cell in cells[1:]:
        numbers, _flag = parse_numbers(cell)
        if numbers:
            return numbers[0]
    numbers, _flag = parse_numbers(cells[0])
    return numbers[0] if numbers else None


def select_and_extract(question: str, client, tools: Tools, k: int = 200,
                       choices: int = 12) -> dict:
    hits = tools.search_expanded(question, k=k)
    unique: dict[str, dict] = {}
    for hit in hits:
        unit = tools._by_id.get(hit["unit_id"])
        if unit is None or getattr(unit, "source", "") != "docling-row":
            continue                       # labels come from table rows only
        label = hit["quote"].split(" | ")[0].strip()
        if not label or label in unique:
            continue
        # prefer the copy from a primary statement over one in the notes
        if "notes to" in getattr(unit, "section", "").lower():
            unique.setdefault(label, hit)
        else:
            unique[label] = hit
    candidates = list(unique.items())[:choices]
    if not candidates:
        return {"question": question, "answer": "", "citations": [],
                "verification": {"status": "declined", "accepted": False,
                                 "failures": [], "numbers": []},
                "choice": None, "candidates": 0}

    listing = "\n".join(f"{i}. {label}" for i, (label, _hit) in enumerate(candidates, start=1))
    text, _usage = client.complete(
        [{"role": "user", "content": PROMPT.format(question=question, choices=listing)}])
    turn = parse_turn(text) or {}
    choice = turn.get("choice")

    if not isinstance(choice, int) or not 1 <= choice <= len(candidates):
        return {"question": question, "answer": "", "citations": [],
                "verification": {"status": "declined", "accepted": False,
                                 "failures": [], "numbers": []},
                "choice": choice, "candidates": len(candidates)}

    label, hit = candidates[choice - 1]
    value = _value_of(hit["quote"])
    if value is None:
        return {"question": question, "answer": "", "citations": [],
                "verification": {"status": "declined", "accepted": False,
                                 "failures": [], "numbers": []},
                "choice": choice, "candidates": len(candidates)}

    unit = tools._by_id[hit["unit_id"]]
    answer = f"The {label.lower()} was {value:,.0f}."
    verification = verify_answer(answer, [unit.unit_id], tools._by_id,
                                 headers=tools._headers, question=question)
    return {"question": question, "answer": answer, "citations": [unit.unit_id],
            "verification": verification, "choice": choice,
            "candidates": len(candidates), "label": label}
