"""The probe set, with gold answers and the evidence each one requires.

Three types, chosen so that "answered" cannot be confused with "guessed":

``total``        a consolidated figure composed of every disclosure cell;
``cell``         one disclosure cell;
``wrong_period`` the same question about a year the corpus does not cover.

The last is unanswerable by construction. A citation-first system must decline
it: there is no unit to cite, and an answer without a citation is not allowed.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass

from .documents import Corpus
from .estate import CELL_METRIC, GROUP_METRIC, PERIOD, SCALE, UNIT
from .facts import FactKey
from .units import Unit, build_units

MISSING_PERIOD = "FY2023"


@dataclass(frozen=True)
class Probe:
    qid: str
    text: str
    type: str
    counterparty: str
    scope: str | None
    gold: int | None
    required_scopes: tuple[str, ...]     # scopes that must be cited

    def as_dict(self) -> dict:
        return {
            "qid": self.qid, "text": self.text, "type": self.type,
            "counterparty": self.counterparty, "scope": self.scope,
            "gold": self.gold, "required_scopes": list(self.required_scopes),
        }


def build_probes(corpus: Corpus) -> list[Probe]:
    cells: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for key, fact in corpus.facts.items():
        if key.metric == CELL_METRIC and fact.value is not None:
            cells[key.entity].append((key.scope, fact.value))

    probes: list[Probe] = []
    for cp in sorted(cells):
        scopes = sorted(s for s, _ in cells[cp])
        total = sum(v for _, v in cells[cp])
        probes.append(Probe(
            qid=f"T-{cp}", type="total", counterparty=cp, scope=None,
            text=f"What is the total exposure for {cp} for {PERIOD}?",
            gold=total, required_scopes=tuple(scopes)))
        scope = scopes[0]
        value = next(v for s, v in cells[cp] if s == scope)
        probes.append(Probe(
            qid=f"C-{cp}", type="cell", counterparty=cp, scope=scope,
            text=(f"What is the exposure for {cp} in the {scope.split('/')[0]} "
                  f"{scope.split('/')[1]} desk for {PERIOD}?"),
            gold=value, required_scopes=(scope,)))
        probes.append(Probe(
            qid=f"P-{cp}", type="wrong_period", counterparty=cp, scope=None,
            text=f"What is the total exposure for {cp} for {MISSING_PERIOD}?",
            gold=None, required_scopes=()))
    return probes


def probe_digest(probes: list[Probe]) -> str:
    blob = json.dumps([p.as_dict() for p in sorted(probes, key=lambda p: p.qid)],
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()
