"""Citeable units — the things an answer is allowed to point at.

Citation-first retrieval changes the unit of retrieval. A conventional pipeline
retrieves *passages* and then hopes the generator cites them. This one retrieves
**citeable units**: a span of a document with a page, a bounding box and a
quote, so that every retrieved thing can be shown to the reader and checked
against the source.

A unit is exactly one observation from the corpus, promoted from evidence to the
retrieval index. That means the retriever's output type *is* the citation type —
there is no conversion step in which a citation can be lost or invented.

Reference point: ALCE (Gao et al., 2023) makes citation a first-class output and
scores it; this module takes the prior step and makes it a first-class *input*.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .documents import Corpus
from .facts import FactKey


@dataclass(frozen=True)
class Unit:
    """One citeable span."""

    uid: str
    doc_id: str
    page: int
    bbox: tuple[float, float, float, float]
    quote: str
    channel: str            # text | table | figure
    value: int | None
    extraction: str         # layout | oracle
    entity: str
    metric: str
    period: str
    scope: str

    def as_dict(self) -> dict:
        return {
            "uid": self.uid, "doc_id": self.doc_id, "page": self.page,
            "bbox": list(self.bbox), "quote": self.quote,
            "channel": self.channel, "value": self.value,
            "extraction": self.extraction, "entity": self.entity,
            "metric": self.metric, "period": self.period, "scope": self.scope,
        }


def _uid(doc_id: str, page: int, channel: str, value: int | None) -> str:
    return f"U:{doc_id}:{page}:{channel}:{value}"


def build_units(corpus: Corpus) -> list[Unit]:
    """Every observation becomes a unit, with its fact key flattened onto it."""
    units: list[Unit] = []
    for key, fact in sorted(corpus.facts.items()):
        for obs in fact.observations:
            units.append(Unit(
                uid=_uid(obs.doc_id, obs.page, obs.channel, obs.value),
                doc_id=obs.doc_id, page=obs.page, bbox=obs.bbox,
                quote=obs.quote, channel=obs.channel, value=obs.value,
                extraction=obs.extraction,
                entity=key.entity, metric=key.metric,
                period=key.period, scope=key.scope,
            ))
    return units


def by_scope(units: Iterable[Unit], entity: str) -> dict[str, list[Unit]]:
    out: dict[str, list[Unit]] = {}
    for unit in units:
        if unit.entity != entity:
            continue
        out.setdefault(unit.scope, []).append(unit)
    return out


def required_for_total(units: Iterable[Unit], counterparty: str) -> dict[str, list[Unit]]:
    """The cells a total is composed of, keyed by scope.

    A total question is covered only when every one of these scopes has at least
    one cited unit — the coverage check that replaces the permission check.
    """
    cells = [u for u in units
             if u.entity == counterparty and u.metric == "cell_exposure"]
    out: dict[str, list[Unit]] = {}
    for unit in cells:
        out.setdefault(unit.scope, []).append(unit)
    return out


def fact_key_of(unit: Unit) -> FactKey:
    return FactKey(unit.entity, unit.metric, unit.period, unit.scope,
                   "HKD", "million")
