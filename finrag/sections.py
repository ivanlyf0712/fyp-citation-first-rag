"""Attach section context to units, from the headings already in the corpus.

Contextual retrieval (Anthropic, 2024) prepends document context to each chunk
before embedding; the reported effect is a 35% cut in top-20 retrieval failures.
The equivalent here is cheaper: the headings are already parsed as text units, so
each unit can inherit the nearest heading above it on the page.

The point is scope. "Operating expenses" on the primary statement is the Group's;
the same label in the notes belongs to a segment or a subsidiary. Without the
section, a retriever cannot tell them apart, and a citation check cannot either.
"""

from __future__ import annotations

import re

HEADING_MAX = 90
_MARKER = re.compile(r"^(?:[IVX]+\.|\(\w+\)|\d+\.|Notes to|\(Unit:|[A-Z][A-Z0-9 ,&()'’\-]+$)")


def is_heading(unit) -> bool:
    """A short, unpunctuated line that looks like a title rather than prose."""
    if unit["channel"] != "text":
        return False
    quote = unit["quote"].strip()
    if not quote or len(quote) > HEADING_MAX or quote.endswith("."):
        return False
    letters = [c for c in quote if c.isalpha()]
    upper_ratio = sum(c.isupper() for c in letters) / max(1, len(letters))
    return bool(_MARKER.match(quote)) or upper_ratio > 0.6


def attach_sections(units: list[dict]) -> list[dict]:
    """Give every unit the nearest heading above it on its page (in place)."""
    pages: dict[tuple, list[dict]] = {}
    for unit in units:
        pages.setdefault((unit.get("doc"), unit.get("page")), []).append(unit)

    for page_units in pages.values():
        headings = sorted((u for u in page_units if is_heading(u)),
                          key=lambda u: -u["bbox"][3])
        for unit in page_units:
            top = unit["bbox"][3]
            section = next((h for h in headings if h["bbox"][3] >= top - 1.0), None)
            unit["section"] = (section["quote"][:HEADING_MAX] if section else "")
    return units
