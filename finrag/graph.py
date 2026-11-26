"""A graph over units, built from what the parser already knows.

The purpose is scope. A row called "Operating expenses" exists on the primary
statement (the Group's) and again in the notes (a segment's). String checks cannot
tell them apart, because the text is the same. The graph links them, so a
retriever can say: this row has a twin on page 18, in the income statement, and
that twin is the one a Group question wants.

Edges:
  * **same label** — rows whose first cell matches, across pages
  * **same table** — rows sharing a table block (from tables.py)
  * **same section** — rows under the same heading

Nodes are unit ids; nothing is learned, and the graph is rebuilt from units in
milliseconds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .tables import table_blocks

PRIMARY = ("consolidated statement", "statement of financial position",
           "key accounting data", "analysis of financial statements",
           "summary of accounting", "statement of profit or loss")


def label_of(quote: str) -> str:
    return quote.split(" | ")[0].strip().lower()


def is_primary(unit) -> bool:
    section = getattr(unit, "section", "").lower()
    return any(hint in section for hint in PRIMARY)


@dataclass
class UnitGraph:
    by_label: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    by_block: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    units: dict[str, object] = field(default_factory=dict)

    @classmethod
    def build(cls, units: list) -> "UnitGraph":
        graph = cls()
        for unit in units:
            graph.units[unit.unit_id] = unit
            if getattr(unit, "source", "") == "docling-row":
                graph.by_label[label_of(unit.quote)].append(unit.unit_id)
        for number, block in enumerate(table_blocks(units)):
            for unit in block:
                graph.by_block[unit.unit_id] = number
        return graph

    def twins(self, unit_id: str) -> list:
        """Rows with the same label elsewhere in the document, best scope first."""
        unit = self.units.get(unit_id)
        if unit is None:
            return []
        ids = [uid for uid in self.by_label.get(label_of(unit.quote), [])
               if uid != unit_id]
        rows = [self.units[uid] for uid in ids]
        rows.sort(key=lambda u: (not is_primary(u), u.page))
        return rows

    def primary_twin(self, unit_id: str):
        for row in self.twins(unit_id):
            if is_primary(row):
                return row
        return None

    def neighbours(self, unit_id: str, limit: int = 10) -> list:
        """Same-table rows plus same-label twins, deduplicated."""
        unit = self.units.get(unit_id)
        if unit is None:
            return []
        block = self.by_block.get(unit_id)
        same_table = [u for uid, u in self.units.items()
                      if block is not None and self.by_block.get(uid) == block
                      and uid != unit_id]
        seen, out = set(), []
        for row in [*self.twins(unit_id), *same_table]:
            if row.unit_id in seen:
                continue
            seen.add(row.unit_id)
            out.append(row)
        return out[:limit]
