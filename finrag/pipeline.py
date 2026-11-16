"""Citation-first retrieval.

Two pipelines over the same corpus, differing in one decision:

**passage-first** — retrieve the top-k *pages*, read whatever facts appear on
them, and answer. This is the conventional retrieval shape: relevance decides
what is read, and the coverage of the answer is whatever the top-k happened to
contain.

**citation-first** — retrieve *units*, require that every scope the claim needs
is among the retrieved and cited units, and refuse when it is not. Retrieval and
citation are the same object, so an answer cannot be produced from evidence that
was not retrieved and shown.

The difference is observable on aggregate questions: passage-first sums a subset
and returns it as the total; citation-first either has all nine cells or says it
does not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .citations import Citation, Coverage, Verdict, verify
from .documents import Corpus
from .estate import CELL_METRIC, COUNTERPARTIES, DESKS, ENTITIES, PERIOD
from .probes import Probe
from .retrieve import Bm25Index, Chunk
from .units import Unit, build_units, required_for_total

CITATION_FIRST = "citation_first"
PASSAGE_FIRST = "passage_first"


@dataclass
class Answer:
    question: str
    mode: str
    status: str                       # answered | refused | not_found
    value: int | None
    citations: list[Citation] = field(default_factory=list)
    coverage: Coverage | None = None
    verdict: Verdict | None = None
    explanation: str = ""
    retrieved: int = 0

    def as_dict(self) -> dict:
        return {
            "question": self.question, "mode": self.mode, "status": self.status,
            "value": self.value,
            "citations": [c.as_dict() for c in self.citations],
            "coverage": self.coverage.as_dict() if self.coverage else None,
            "verdict": self.verdict.as_dict() if self.verdict else None,
            "explanation": self.explanation,
            "retrieved": self.retrieved,
        }


def _scope_of(question: str) -> tuple[str | None, str | None]:
    entity = next((e for e in ENTITIES if re.search(rf"\b{e}\b", question)), None)
    desk = next((d for d in DESKS if re.search(rf"\b{d}\b", question, re.I)), None)
    return entity, desk


class CitationFirst:
    """Both pipelines, over one corpus."""

    def __init__(self, corpus: Corpus, out_dir, k_pages: int = 5, k_units: int = 40):
        #: retrieval depth for units; the k-sweep in run_eval varies this
        self.corpus = corpus
        self.units: list[Unit] = build_units(corpus)
        self.by_uid = {u.uid: u for u in self.units}
        self.k_pages = k_pages
        self.k_units = k_units

        self.page_index = Bm25Index.from_corpus(corpus, out_dir)
        self.unit_index = Bm25Index()
        for unit in self.units:
            # the scope and metric are searchable too: a query names the cell
            text = f"{unit.quote} {unit.scope} {unit.metric} {unit.entity}"
            self.unit_index.add(Chunk(doc_id=unit.uid, page=unit.page, text=text))
        self.unit_index.finalize()

    # -- retrieval ---------------------------------------------------------
    def retrieve_units(self, question: str) -> list[Unit]:
        ranked = self.unit_index.ranked_docs(question, k=self.k_units)
        return [self.by_uid[uid] for uid in ranked if uid in self.by_uid]

    def retrieve_pages(self, question: str) -> set[tuple[str, int]]:
        return {(doc, page) for doc, page, _ in
                self.page_index.search(question, k=self.k_pages)}

    # -- answering ---------------------------------------------------------
    def ask(self, question: str, mode: str = CITATION_FIRST) -> Answer:
        # A period the corpus does not cover has no units at all, so the honest
        # answer is a refusal. This is a shared capability, not a property of
        # either retrieval order: both pipelines get the same check.
        asked = re.search(r"\bFY\s?(\d{4})\b", question, re.I)
        if asked and f"FY{asked.group(1)}" != PERIOD:
            return Answer(question, mode, "refused", None,
                          explanation=(f"the corpus covers {PERIOD} only; no unit "
                                       f"can be cited for FY{asked.group(1)}"))

        cp = next((c for c in COUNTERPARTIES if c.lower() in question.lower()), None)
        if cp is None:
            return Answer(question, mode, "unparseable", None,
                          explanation="no counterparty named in the question")
        entity, desk = _scope_of(question)
        if entity and desk:
            return self._cell(question, mode, cp, f"{entity}/{desk}")
        return self._total(question, mode, cp)

    def _cell(self, question: str, mode: str, cp: str, scope: str) -> Answer:
        if mode == CITATION_FIRST:
            retrieved = self.retrieve_units(question)
            match = [u for u in retrieved
                     if u.entity == cp and u.metric == CELL_METRIC and u.scope == scope]
            if not match:
                return Answer(question, mode, "refused", None, retrieved=len(retrieved),
                              explanation=(f"no citeable unit for {cp} {scope} was "
                                           f"retrieved, so there is nothing to cite"))
            unit = match[0]
            return self._answered(question, mode, unit.value, [unit], None, 1)

        pages = self.retrieve_pages(question)
        hits = [u for u in self.units
                if u.entity == cp and u.metric == CELL_METRIC
                and u.scope == scope and (u.doc_id, u.page) in pages]
        if not hits:
            return Answer(question, mode, "not_found", None,
                          explanation="the evidence was not on any retrieved page")
        return self._answered(question, mode, hits[0].value, [hits[0]], None, len(pages))

    def _total(self, question: str, mode: str, cp: str) -> Answer:
        required = required_for_total(self.units, cp)
        if mode == CITATION_FIRST:
            retrieved = self.retrieve_units(question)
            best: dict[str, Unit] = {}
            for unit in retrieved:
                if unit.entity == cp and unit.metric == CELL_METRIC:
                    best.setdefault(unit.scope, unit)
            missing = [s for s in required if s not in best]
            coverage = Coverage(ok=not missing, required=sorted(required),
                                covered=sorted(best), missing=missing)
            if missing:
                return Answer(question, mode, "refused", None, coverage=coverage,
                              retrieved=len(retrieved),
                              explanation=(f"cannot answer: {len(missing)} of "
                                           f"{len(required)} contributing cells were "
                                           f"not retrieved and cannot be cited "
                                           f"({', '.join(missing[:3])}"
                                           f"{'…' if len(missing) > 3 else ''})"))
            cited_units = [best[s] for s in sorted(required)]
            value = sum(u.value for u in cited_units)
            return self._answered(question, mode, value, cited_units, required,
                                  len(retrieved), coverage)

        pages = self.retrieve_pages(question)
        hits: dict[str, Unit] = {}
        for unit in self.units:
            if (unit.entity == cp and unit.metric == CELL_METRIC
                    and (unit.doc_id, unit.page) in pages):
                hits.setdefault(unit.scope, unit)
        if not hits:
            return Answer(question, mode, "not_found", None,
                          explanation="no contributing unit was on a retrieved page")
        value = sum(u.value for u in hits.values())
        coverage = Coverage(ok=len(hits) == len(required), required=sorted(required),
                            covered=sorted(hits),
                            missing=[s for s in required if s not in hits])
        return Answer(question, mode, "answered", value,
                      citations=[Citation.of(hits[s]) for s in sorted(hits)],
                      coverage=coverage, retrieved=len(pages),
                      explanation=(f"summed the {len(hits)} cells that appeared on "
                                   f"the top {len(pages)} pages"))

    # -- shared ------------------------------------------------------------
    def _answered(self, question: str, mode: str, value: int,
                  units: list[Unit], required, retrieved: int,
                  coverage: Coverage | None = None) -> Answer:
        citations = [Citation.of(u) for u in units]
        derivation = [u.value for u in units]
        verdict = verify(value, citations,
                         {s: [] for s in required} if required else None,
                         units, derivation)
        return Answer(question, mode, "answered", value, citations=citations,
                      coverage=coverage or verdict.coverage, verdict=verdict,
                      retrieved=retrieved,
                      explanation=(f"sum of {len(units)} cited units"
                                   if len(units) > 1 else
                                   f"stated in {units[0].doc_id} p{units[0].page}"))


def run_probe(pipeline: CitationFirst, probe: Probe, mode: str) -> dict:
    answer = pipeline.ask(probe.text, mode)
    return answer.as_dict() | {
        "qid": probe.qid, "type": probe.type, "gold": probe.gold,
        "required_scopes": list(probe.required_scopes),
    }
