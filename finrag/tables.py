"""Group row units into the tables they came from.

A row alone cannot be judged: `Operating expenses | 26,325 | 26,033` looks exactly
like `Operating expenses | 10,488,740 | 10,713,146` until you see the adjacent
rows and the section. Blocks are built from geometry — rows on one page, close
together vertically and starting at the same x — because the parser does not
expose table ids.
"""

from __future__ import annotations

MAX_GAP = 8.0          # points between consecutive rows of one table
MAX_LEFT_SHIFT = 24.0  # a block that jumps sideways is a different table


def table_blocks(units: list) -> list[list]:
    """Rows grouped into tables, from the geometry of their boxes."""
    by_page: dict[tuple, list] = {}
    for unit in units:
        if getattr(unit, "source", "") == "docling-row":
            by_page.setdefault((unit.doc, unit.page), []).append(unit)

    blocks: list[list] = []
    for page_rows in by_page.values():
        page_rows.sort(key=lambda u: -u.bbox[3])       # top of page first
        current: list = []
        for unit in page_rows:
            if not current:
                current = [unit]
                continue
            previous = current[-1]
            gap = previous.bbox[1] - unit.bbox[3]
            shift = abs(previous.bbox[0] - unit.bbox[0])
            if gap <= MAX_GAP and shift <= MAX_LEFT_SHIFT:
                current.append(unit)
            else:
                blocks.append(current)
                current = [unit]
        if current:
            blocks.append(current)
    return blocks


def block_index(units: list) -> dict[str, int]:
    """unit_id -> block number, for every row unit."""
    out: dict[str, int] = {}
    for number, block in enumerate(table_blocks(units)):
        for unit in block:
            out[unit.unit_id] = number
    return out
