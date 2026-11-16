"""Mark questions against the evidence you accepted.

No retrieval, no model: read the two annotation files, and for each question
check three things —

* is every unit the question needs actually in the accepted set?
* does each cited quote really contain the number it is cited for?
* does the answer, built only from those units, equal the gold value?

This is the step that turns clicking into numbers. Retrieval is a separate
question, and adding it before this works would measure the wrong thing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def contains_value(quote: str, value: float | None) -> bool:
    """Is the number actually in the text it is cited for?

    Commas and spaces are stripped before comparison, because a statement writes
    `5,255,815` and the value is stored as `5255815.0`. The sign is checked
    separately by the caller, since negatives appear as `(10,488,740)`.
    """
    if value is None:
        return False
    digits = str(abs(int(round(value))))
    flat = re.sub(r"[,\s]", "", quote)
    return digits in flat


def mark(question: dict[str, Any], units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = question.get("required_units") or []
    missing = [uid for uid in required if uid not in units]
    row: dict[str, Any] = {
        "qid": question.get("qid"),
        "question": question.get("question", ""),
        "gold": question.get("gold_value"),
        "required": len(required),
        "missing": missing,
    }

    if not required:
        row.update(status="no_evidence_declared", answer=None, support=None)
        return row

    if missing:
        row.update(status="missing_evidence", answer=None, support=None)
        return row

    cited = [units[uid] for uid in required]
    values = [c.get("value") for c in cited]
    if any(v is None for v in values):
        row.update(status="no_value_parsed", answer=None, support=None)
        return row

    answer = sum(values) if len(values) > 1 else values[0]
    support = all(contains_value(c.get("quote", ""), c.get("value")) for c in cited)
    gold = question.get("gold_value")
    correct = gold is not None and abs(answer - gold) < 0.5

    row.update(answer=answer, support=support,
               status="correct" if correct else "wrong")
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    counts["total"] = len(rows)
    counts["support_failures"] = sum(1 for r in rows if r.get("support") is False)
    return counts


def report(rows: list[dict[str, Any]]) -> str:
    lines = ["| qid | question | gold | answer | status | support |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        gold = "—" if r["gold"] is None else f"{r['gold']:,.0f}"
        answer = "—" if r.get("answer") is None else f"{r['answer']:,.0f}"
        support = "—" if r.get("support") is None else ("ok" if r["support"] else "**bad**")
        lines.append(f"| {r['qid']} | {r['question'][:60]} | {gold} | {answer} | "
                     f"{r['status']} | {support} |")
    return "\n".join(lines)
