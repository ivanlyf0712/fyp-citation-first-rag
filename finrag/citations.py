"""Citations, coverage, and the verification of an answer against its evidence.

The rule this module enforces is the whole method in one sentence:

> **An answer may contain only numbers that its citations support.**

Two checks implement it.

*Coverage* asks whether the cited units are *sufficient*: for an aggregate, has
every contributing cell been cited? For a single figure, has the figure's own
unit been cited?

*Support* asks whether the cited units are *necessary and correct*: does each
number in the answer appear in a cited quote, and does the arithmetic follow
from the cited values?

A claim that fails either check is not returned as an answer. That is stricter
than post-hoc citation scoring (ALCE), where the answer exists first and the
citations are graded afterwards — here an unciteable answer is never produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from .units import Unit

_NUMBER = re.compile(r"\d[\d,]*")


@dataclass(frozen=True)
class Citation:
    uid: str
    doc_id: str
    page: int
    bbox: tuple[float, float, float, float]
    quote: str
    channel: str
    value: int | None

    @classmethod
    def of(cls, unit: Unit) -> "Citation":
        return cls(unit.uid, unit.doc_id, unit.page, unit.bbox,
                   unit.quote, unit.channel, unit.value)

    def as_dict(self) -> dict:
        return {
            "uid": self.uid, "doc_id": self.doc_id, "page": self.page,
            "bbox": list(self.bbox), "quote": self.quote,
            "channel": self.channel, "value": self.value,
        }


@dataclass
class Coverage:
    ok: bool
    required: list[str] = field(default_factory=list)
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        if not self.required:
            return 1.0
        return len(self.covered) / len(self.required)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "required": len(self.required),
                "covered": len(self.covered), "missing": self.missing,
                "ratio": round(self.ratio, 3)}


@dataclass
class Verdict:
    supported: bool
    coverage: Coverage
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"supported": self.supported, "coverage": self.coverage.as_dict(),
                "checks": self.checks, "failures": self.failures}


def check_coverage(required: dict[str, list[Unit]],
                   cited: Iterable[Unit]) -> Coverage:
    """Is every required scope represented among the cited units?"""
    cited_scopes = {u.scope for u in cited}
    need = sorted(required)
    missing = [s for s in need if s not in cited_scopes]
    return Coverage(ok=not missing, required=need,
                    covered=[s for s in need if s in cited_scopes],
                    missing=missing)


def check_support(value: int | None, citations: Iterable[Citation],
                  derivation: Iterable[int] = ()) -> tuple[bool, list[str], list[str]]:
    """Does the answer follow from what was cited?

    A cited unit's value must actually appear in its own quote — the quote is
    the evidence, and a bbox that points at a number the text does not contain
    is a false citation. Then the answer must equal the sum of the values cited
    for the derivation (or the single cited value).
    """
    checks: list[str] = []
    failures: list[str] = []
    cites = list(citations)

    for c in cites:
        if c.value is not None and str(c.value) not in c.quote:
            failures.append(f"{c.uid}: quote does not contain {c.value}")

    if value is not None:
        parts = [v for v in derivation if v is not None]
        if parts and sum(parts) != value:
            failures.append(f"derivation sums to {sum(parts)}, answer is {value}")
        elif not parts and cites:
            single = [c.value for c in cites if c.value is not None]
            if single and value not in single:
                failures.append(f"answer {value} is not among the cited values {single}")

    checks.append(f"{len(cites)} citations checked")
    return (not failures, checks, failures)


def verify(value: int | None, citations: list[Citation],
           required: dict[str, list[Unit]] | None,
           cited_units: list[Unit],
           derivation: list[int]) -> Verdict:
    coverage = (check_coverage(required, cited_units)
                if required is not None else Coverage(ok=True))
    supported, checks, failures = check_support(value, citations, derivation)
    if not coverage.ok:
        failures.append(f"coverage {coverage.ratio:.0%}: missing {coverage.missing}")
    return Verdict(supported=supported and coverage.ok, coverage=coverage,
                   checks=checks, failures=failures)
