"""The agentic answer layer: tools, a hand-written loop, and enforcement.

The model chooses tools and writes the prose. What it may **not** do is invent a
number: after it answers, every figure in the sentence is looked up in the
quotes it cited, and the answer is withheld if one is missing. That is the same
bargain as the citation-first pipeline, moved one layer up — from "which units
may I answer from" to "may I say this sentence at all".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .ingest import parse_numbers
from .retrieve import Bm25Index, Chunk

MAX_TOOL_CALLS = 6
YEAR = re.compile(r"\b(19|20)\d{2}\b")
_MONTHS = ("January|February|March|April|May|June|July|August|September|"
           "October|November|December")
# both orders appear in filings: "31 December 2024" and "December 31, 2024"
DATE = re.compile(
    rf"\b(?:\d{{1,2}}\s+(?:{_MONTHS})|(?:{_MONTHS})\s+\d{{1,2}}),?\s*\d{{0,4}}\b",
    re.I)

SYSTEM_PROMPT = """You answer questions about financial documents using tools.

Reply with ONE JSON object per turn, nothing else.

To use a tool (prefer search_expanded — it rewrites the question and reranks):
{"tool": "search_expanded", "query": "net profit", "k": 5}
{"tool": "search_bm25", "query": "net profit", "k": 5}
{"tool": "search_semantic", "query": "how much did the bank earn", "k": 5}
{"tool": "read_unit", "unit_id": "U:abc123"}
{"tool": "search_expanded", "query": "loans and advances to customers", "k": 5}
{"tool": "find_row", "label": "gross loans and advances to customers"}
{"tool": "read_table", "unit_id": "U:abc123"}
{"tool": "related_rows", "unit_id": "U:abc123"}

To answer:
{"answer": "The Group's net profit was RMB5,255,815 thousand in 2024.",
 "citations": ["U:4bf507ea4a"]}

Rules:
- Financial tables have several numeric columns. The header row says which is
  which, usually 2024 | 2023 | Change. The FIRST numeric column is the current
  year; the second is the prior year. Read the column the question asks for.
- Every number in your answer must appear in a quote you cite.
- Cite only unit ids that a tool returned to you.
- A single row cannot be judged. If a row looks right, call read_table on it to
  see the whole statement, then answer from the row that matches the question.
- If a search returns nothing useful, try search_expanded, which rewrites the
  question into the wording annual reports use ("charge" -> "losses").
- If the evidence does not contain the answer, say so and cite nothing.
- Do not use outside knowledge. Do not guess.
- A figure in the notes may belong to a segment or a subsidiary. If the question
  asks about the Group or the Bank, prefer units whose "section" names a
  primary statement over notes and segment reporting.
"""


EXPAND_PROMPT = """Rewrite the question as three short search queries, using the
wording an annual report would use. Prefer the formal line-item names.
Reply with JSON only: {{"queries": ["...", "...", "..."]}}

Question: {question}"""


PRIMARY_HINTS = ("consolidated statement", "statement of financial position",
                 "key accounting data", "analysis of financial statements",
                 "summary of accounting", "statement of profit or loss")
NOTES_HINT = "notes to"
SEGMENT_HINTS = ("segment", "related part", "by geography", "by business", "subsidiar")

FINANCE_SYNONYMS = {
    "loan": "gross loans and advances to customers",
    "deposit": "gross deposits from customers",
    "impairment": "impairment losses on assets",
    "charge": "impairment losses on assets",
}


def scope_weight(section: str, query: str) -> float:
    """Prefer primary statements over notes for Group-level questions.

    The same label appears on the primary statement (Group) and in the notes
    (segment or subsidiary). Section context is the only thing that separates
    them, so it is used as a ranking prior.
    """
    if not any(word in query.lower() for word in ("group", "bank", "total")):
        return 1.0
    text = (section or "").lower()
    if any(hint in text for hint in PRIMARY_HINTS):
        return 1.8
    if NOTES_HINT in text:
        return 0.7
    return 1.0


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal rank fusion; equal weights, as corpchat's fusion does."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, uid in enumerate(ranking, start=1):
            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda uid: -scores[uid])


def expand_query(client, question: str) -> list[str]:
    """Ask the model for the document's vocabulary; never fail the run for it."""
    try:
        from .llm import parse_turn
        text, _usage = client.complete(
            [{"role": "user", "content": EXPAND_PROMPT.format(question=question)}])
        turn = parse_turn(text) or {}
        variants = [str(v).strip() for v in turn.get("queries", []) if str(v).strip()]
        extra = [canonical for stem, canonical in FINANCE_SYNONYMS.items()
                 if stem in question.lower() and canonical not in variants]
        return list(dict.fromkeys([question] + variants + extra))[:5]
    except Exception:                                    # noqa: BLE001
        return [question]


def unit_view(unit, header: str = "") -> dict[str, Any]:
    view = {"unit_id": unit.unit_id, "doc": unit.doc, "page": unit.page,
            "channel": unit.channel, "numbers": list(unit.numbers),
            "quote": unit.quote[:600]}
    section = getattr(unit, "section", "")
    if section:
        view["section"] = section
    if header and header != unit.quote:
        view["table_header"] = header[:200]
    return view


@dataclass
class Tools:
    units: list
    vector_index: Any | None = None
    expander: Any | None = None
    reranker: Any | None = None
    _by_id: dict = field(init=False, default_factory=dict)
    _bm25: Bm25Index | None = field(init=False, default=None)
    _headers: dict = field(init=False, default_factory=dict)
    _blocks: dict = field(init=False, default_factory=dict)
    _graph: Any | None = field(init=False, default=None)
    _block_list: list = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._by_id = {u.unit_id: u for u in self.units}
        index = Bm25Index()
        for unit in self.units:
            index.add(Chunk(doc_id=unit.unit_id, page=unit.page,
                            text=f"{unit.quote} {unit.channel}"))
        index.finalize()
        self._bm25 = index
        from .graph import UnitGraph
        from .tables import table_blocks
        self._graph = UnitGraph.build(self.units)
        self._block_list = table_blocks(self.units)
        for number, block in enumerate(self._block_list):
            for unit in block:
                self._blocks[unit.unit_id] = number
        # the topmost row on a page is taken to be its table header
        for unit in sorted(self.units, key=lambda u: (-u.bbox[3], u.bbox[0])):
            if getattr(unit, "source", "") == "docling-row":
                self._headers.setdefault((unit.doc, unit.page), unit.quote)

    # -- tool implementations ---------------------------------------------
    def search_bm25(self, query: str, k: int = 5) -> list[dict]:
        hits = self._bm25.ranked_docs(query, k=k)
        out = []
        for uid in hits:
            unit = self._by_id.get(uid)
            if unit:
                out.append(unit_view(unit, self._headers.get((unit.doc, unit.page), "")))
        return out

    def search_semantic(self, query: str, k: int = 5) -> list[dict]:
        if self.vector_index is None:
            return []
        hits = self.vector_index.search(query, k=k)
        out = []
        for uid, _score in hits:
            unit = self._by_id.get(uid)
            if unit:
                out.append(unit_view(unit, self._headers.get((unit.doc, unit.page), "")))
        return out

    def search_expanded(self, query: str, k: int = 5) -> list[dict]:
        """Search every wording of the question and fuse the rankings."""
        variants = self.expander(query) if self.expander else [query]
        rankings: list[list[str]] = []
        for variant in variants:
            bm = self._bm25.ranked_docs(variant, k=20) if self._bm25 else []
            rankings.append(bm)
            if self.vector_index is not None:
                rankings.append([uid for uid, _s in
                                 self.vector_index.search(variant, k=20)])
        rankings = [r for r in rankings if r]
        if not rankings:
            return []
        fused = [uid for uid in rrf_fuse(rankings) if uid in self._by_id]
        if any(w in query.lower() for w in ("group", "bank", "total")):
            position = {uid: i for i, uid in enumerate(fused)}
            fused.sort(key=lambda uid: -(
                1.0 / (60 + position[uid] + 1)
                * scope_weight(getattr(self._by_id[uid], "section", ""), query)))
        if self.reranker is not None and fused:
            candidates = fused[:30]
            pairs = [(query, self._by_id[uid].quote) for uid in candidates]
            try:
                scores = self.reranker.predict(pairs)
                order = sorted(range(len(candidates)), key=lambda i: -float(scores[i]))
                fused = [candidates[i] for i in order] + fused[30:]
            except Exception:                            # noqa: BLE001
                pass
        return [unit_view(self._by_id[uid], self._headers.get(
                    (self._by_id[uid].doc, self._by_id[uid].page), ""))
                for uid in fused[:k]]

    def find_row(self, label: str, k: int = 5) -> list[dict]:
        """Match a line-item name against row labels only.

        Statements name things in their own vocabulary — "gross loans and
        advances to customers" — and a question says "loans". Searching whole
        rows buries the label among numbers; this searches the label alone.
        """
        words = [w for w in re.findall(r"[a-z]{3,}", label.lower())
                 if w not in STOPWORDS]
        if not words:
            return []
        scored = []
        for unit in self.units:
            if getattr(unit, "source", "") != "docling-row":
                continue
            text = unit.quote.split(" | ")[0].lower()
            hits = sum(1 for w in words if w in text)
            if hits:
                scored.append((hits / len(words), unit))
        scored.sort(key=lambda pair: -pair[0])
        return [unit_view(unit, self._headers.get((unit.doc, unit.page), ""))
                for _score, unit in scored[:k]]

    def related_rows(self, unit_id: str, limit: int = 8) -> list[dict]:
        """Rows linked to this one: same label elsewhere, then the same table."""
        if self._graph is None:
            return []
        return [unit_view(u, self._headers.get((u.doc, u.page), ""))
                for u in self._graph.neighbours(unit_id, limit=limit)]

    def read_table(self, unit_id: str, limit: int = 40) -> dict:
        """Every row of the table the given row belongs to."""
        number = self._blocks.get(unit_id)
        if number is None:
            return {"error": f"{unit_id} is not a table row"}
        block = self._block_list[number]
        header = self._headers.get((block[0].doc, block[0].page), "")
        return {"section": getattr(block[0], "section", ""),
                "header": header[:200],
                "rows": [{"unit_id": u.unit_id, "row": u.quote[:200]}
                         for u in block[:limit]],
                "total_rows": len(block)}

    def read_unit(self, unit_id: str) -> dict:
        unit = self._by_id.get(unit_id)
        if not unit:
            return {"error": f"unknown unit {unit_id}"}
        return unit_view(unit, self._headers.get((unit.doc, unit.page), ""))

    def call(self, name: str, args: dict) -> dict:
        if name == "search_semantic" and self.vector_index is None:
            return {"error": "semantic index not loaded for this run; use search_bm25"}
        if name == "search_bm25":
            return {"units": self.search_bm25(str(args.get("query", "")),
                                              int(args.get("k", 5)))}
        if name == "search_semantic":
            return {"units": self.search_semantic(str(args.get("query", "")),
                                                  int(args.get("k", 5)))}
        if name == "related_rows":
            return {"units": self.related_rows(str(args.get("unit_id", "")))}
        if name == "read_table":
            return self.read_table(str(args.get("unit_id", "")))
        if name == "find_row":
            return {"units": self.find_row(str(args.get("label", "")),
                                           int(args.get("k", 5)))}
        if name == "search_expanded":
            return {"units": self.search_expanded(str(args.get("query", "")),
                                                  int(args.get("k", 5)))}
        if name == "read_unit":
            return {"unit": self.read_unit(str(args.get("unit_id", "")))}
        return {"error": f"unknown tool {name}"}


# --------------------------------------------------------------------------
# enforcement
# --------------------------------------------------------------------------
def answer_numbers(text: str) -> list[float]:
    """Numbers in the prose, ignoring years ("in 2024", "2,024").

    Commas are removed before the year test so a comma-formatted year is still
    recognised as a year. The cost: a genuine quantity of 2024 would also be
    dropped — rare enough to accept, and noted rather than hidden.
    """
    flat = DATE.sub(" ", text).replace(",", "")
    cleaned = YEAR.sub(" ", flat)
    values, _flag = parse_numbers(cleaned)
    return values


DECLINE = re.compile(
    r"does not (?:contain|state|show)|cannot|can't|no (?:figure|line item|evidence|explicit)"
    r"|not explicitly|unable to", re.I)


YEAR_IN_QUESTION = re.compile(r"\b(20\d{2})\b")


YEAR_CELL = re.compile(r"^(?:19|20)\d{2}$")


def column_map(header: str, row_quote: str):
    """(year, column index in the row) pairs — or None if the table is not safely readable.

    A table is only used when its header parses into years and its width matches
    the row's cell count. Merged headers, stacked years and side-by-side tables
    fail that test, and a check that guesses on them rejects correct answers —
    which is exactly what happened before this guard existed.
    """
    if "|" not in header or "|" not in row_quote:
        return None
    head = [c.strip() for c in header.split("|")]
    row = [c.strip() for c in row_quote.split("|")]
    year_cols = [(i, c) for i, c in enumerate(head) if YEAR_CELL.match(c)]
    if not year_cols:
        return None
    offset = len(row) - len(head)
    if offset not in (0, 1):
        return None
    return [(year, index + offset) for index, year in year_cols]


def column_failures(question: str, cited: list, numbers: list[float],
                    headers: dict) -> list[str]:
    """Is the primary number in the column of the year the question names?

    A row holds every year side by side, so "the quote contains 5,080,903" is
    true whether the question asked 2024 or 2023. The header says which column is
    which. Only the first number is a column claim; the rest ("up 3.44%") merely
    have to be in the row, which the support check already covers. Values are
    compared with scale tolerance, so "5,256 million" satisfies a cell holding
    "5,255,815" thousand.
    """
    years = YEAR_IN_QUESTION.findall(question or "")
    if not numbers or not years:
        return []
    year = years[0]

    for unit in cited:
        mapping = column_map(headers.get((unit.doc, unit.page), ""), unit.quote)
        if not mapping:
            continue                    # table not safely readable: never reject on it
        target = next(((y, i) for y, i in mapping if y == year), None)
        if target is None:
            continue
        _year, index = target
        row_cells = [c.strip() for c in unit.quote.split("|")]
        if index >= len(row_cells):
            continue
        cell = row_cells[index]
        cell_numbers, _flag = parse_numbers(cell)
        claim = numbers[0]
        if any(value_matches(claim, n) for n in cell_numbers):
            return []                   # one cited row confirms the column
        return [f"{claim:g} not in the {year} column of {unit.unit_id} "
                f"(that column holds {cell or 'nothing'})"]
    return []


def verify_answer(answer: str, citations: list[str], units: dict,
                  headers: dict | None = None, question: str = "") -> dict:
    """Is this sentence supported by the units it cites?"""
    failures: list[str] = []
    cited = [units[c] for c in citations if c in units]
    missing = [c for c in citations if c not in units]
    if missing:
        failures.append(f"citations unknown: {missing}")

    numbers = answer_numbers(answer)
    if DECLINE.search(answer) and not citations:
        return {"status": "declined", "accepted": False, "failures": [],
                "numbers": numbers}
    if not numbers:
        return {"status": "declined", "accepted": False, "failures": [],
                "numbers": []}

    if not cited:
        failures.append("answer states a number but cites nothing")
        return {"status": "rejected", "accepted": False, "failures": failures,
                "numbers": numbers}

    allowed: list[float] = []
    for unit in cited:
        allowed.extend(abs(v) for v in unit.numbers)
    # scale-aware support: "5,256 million" restates a quote holding 5,255,815
    unsupported = [n for n in numbers
                   if not any(value_matches(n, v) for v in allowed)]
    if unsupported:
        failures.append(f"numbers not in cited quotes: {unsupported}")

    bad_column = False
    segment_users = [u for u in cited
                     if any(h in getattr(u, "section", "").lower()
                            for h in SEGMENT_HINTS)]
    asks_group = any(w in (question or "").lower()
                     for w in ("group", "the bank", "total"))
    if segment_users and asks_group and not any(
            "group" == getattr(u, "scope", "") for u in cited):
        failures.append("a Group-level question cited segment/related-party evidence")

    if headers and not unsupported:
        column = column_failures(question, cited, numbers, headers)
        if column:
            failures.extend(column)
            bad_column = True

    ok = not unsupported and not missing and not bad_column
    return {"status": "accepted" if ok else "rejected",
            "accepted": ok, "failures": failures, "numbers": numbers}


# --------------------------------------------------------------------------
# the loop
# --------------------------------------------------------------------------
def run(question: str, client, tools: Tools, max_calls: int = MAX_TOOL_CALLS,
        enforce: bool = True) -> dict:
    if tools.expander is None:
        tools.expander = lambda q: expand_query(client, q)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}]
    trace: list[dict] = []
    answer, citations = "", []
    repaired = False

    for _step in range(max_calls + 1):
        text, usage = client.complete(messages)
        turn = _parse(text)
        if turn is None:
            if repaired:
                answer, citations = "", []
                break
            repaired = True
            messages += [{"role": "assistant", "content": text},
                         {"role": "user",
                          "content": 'Reply with one JSON object and nothing else.'}]
            continue

        if "answer" in turn:
            answer = str(turn.get("answer", ""))
            citations = [str(c) for c in turn.get("citations", []) or []]
            break

        name = str(turn.get("tool", ""))
        result = tools.call(name, turn)
        trace.append({"tool": name, "args": {k: v for k, v in turn.items()
                                             if k != "tool"},
                      "returned": len(result.get("units", []))})
        messages += [{"role": "assistant", "content": json.dumps(turn)},
                     {"role": "user", "content": json.dumps({"tool_result": result})}]
    else:
        messages.append({"role": "user", "content":
                         'No tool calls left. Answer now with '
                         '{"answer": "...", "citations": ["U:..."]}'})
        text, _usage = client.complete(messages)
        turn = _parse(text) or {}
        answer = str(turn.get("answer", ""))
        citations = [str(c) for c in turn.get("citations", []) or []]

    verification = verify_answer(answer, citations, tools._by_id,
                                 headers=tools._headers, question=question)
    # The draft is what the model said; `answer` is what the user is allowed to
    # see. With enforcement off they are the same, which is exactly the condition
    # the project measures against.
    withheld = enforce and not verification["accepted"]
    return {"question": question,
            "answer": "" if withheld else answer,
            "draft": answer,
            "withheld": withheld,
            "citations": citations,
            "verification": verification, "trace": trace,
            "tool_calls": len(trace),
            "usage": getattr(client, "calls", [])}


def _parse(text: str) -> dict | None:
    from .llm import parse_turn
    return parse_turn(text)


def value_matches(claim: float, gold: float, rel: float = 1e-3) -> bool:
    """Compare a claim with gold, allowing for scale and sign conventions.

    Annual reports mix scales: a table headed `RMB'000` says `5,255,815` while
    the prose beside it says `RMB5,256 million` — the same fact, rounded. And
    expenses appear in parentheses, so the signed value is negative while the
    sentence reads "operating expenses were 10,488,740".

    Both are conventions, not errors, so both are absorbed here. The tolerance
    is 0.1% *of the gold value*, which covers rounding to the nearest million
    without accepting a genuinely different figure.
    """
    g = abs(gold)
    for factor in (1.0, 1e3, 1e6, 1e-3, 1e-6):
        if abs(abs(claim) * factor - g) <= max(0.5, rel * g):
            return True
    return False




STOPWORDS = {"what", "was", "were", "the", "of", "for", "in", "on", "at", "that",
             "this", "how", "much", "did", "does", "do", "a", "an", "and", "or",
             "to", "from", "by", "with", "its", "their", "year", "group", "bank"}


def _label_match(question: str, unit) -> float:
    """How much of the question's vocabulary appears in the row's label."""
    words = {w for w in re.findall(r"[a-z]{3,}", question.lower())
             if w not in STOPWORDS}
    label = {w for w in re.findall(r"[a-z]{3,}", unit.quote.split(" | ")[0].lower())}
    if not words or not label:
        return 0.0
    return len(words & label) / len(words)


def claim_number(question: str, numbers: list[float], cited: list) -> float:
    """The number the sentence is really claiming.

    A good answer can name two real figures from two adjacent rows ("net profit
    5,255,815 ... attributable to ordinary shareholders 4,305,815"). Taking the
    first one punishes the sentence for being complete. Pick the number whose
    cited row best matches the question — and, on a tie, the row from a primary
    statement rather than the notes.
    """
    best, best_score = numbers[0], -1.0
    for number in numbers:
        for unit in cited:
            if not any(value_matches(v, number) for v in unit.numbers):
                continue
            score = _label_match(question, unit)
            if "notes to" not in getattr(unit, "section", "").lower():
                score += 0.25
            if score > best_score:
                best, best_score = number, score
    return best


def score_answer(result: dict, gold: float | None) -> str:
    """One outcome per question: correct / wrong / rejected / declined.

    A rejection is not a wrong answer: the system withheld a claim it could not
    support. Counting the two together would hide exactly the behaviour the
    enforcement exists to produce.
    """
    verification = result["verification"]
    if verification["status"] == "declined":
        return "declined"
    if not verification["accepted"]:
        return "rejected"
    if gold is None:
        return "answered"
    numbers = verification["numbers"]
    if not numbers:
        return "declined"

    # A long answer can mention six figures; only the first is the claim. Taking
    # any match would let an answer that lists a whole row count as correct for
    # every question about that row.
    # Measured alternative: pick the number whose cited row matches the question
    # (claim_number below). It scored 5.3/10 against 6.0 for first-number, so the
    # simple rule stays. The helper is kept because the audit depends on it.
    claim = numbers[0]
    sustained = value_matches(claim, gold)
    if not sustained and DECLINE.search(result.get("answer", "")):
        return "declined"
    return "correct" if sustained else "wrong"
