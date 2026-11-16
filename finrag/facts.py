"""Canonical fact records.

A *fact* is one number with the context needed to compare it to another number:
entity, metric, period, scope, unit and scale. The value is deliberately **not**
part of the identity, so that two documents making the same claim can be
compared — agreement becomes an edge, disagreement becomes an edge, and neither
is averaged away.

This is the design decision that makes the completeness check expressible: a
chunk of text cannot be summed, but a fact whose scope names the partition it
describes can be, because the set of facts contributing to a total is known.

The tuple schema follows the typed-unit evidence graphs in HC-RAG
(arXiv:2608.12335), which distinguishes document / section / text-unit /
table-unit nodes for financial filings. We keep the typing but replace
text units with numeric facts, which is what aggregation needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Channels an observation can come through. `figure` means the number was read
# from pixels, not from a text layer.
CHANNELS = ("text", "table", "figure")

# How the observation was obtained. `layout` means recorded while drawing the
# document (the perfect-extraction condition); `oracle` means read from the
# generator's ground truth rather than from the image.
EXTRACTIONS = ("layout", "oracle")


@dataclass(frozen=True, order=True)
class FactKey:
    """Identity of a claim, excluding its value."""

    entity: str
    metric: str
    period: str
    scope: str
    unit: str
    scale: str

    def as_dict(self) -> dict[str, str]:
        return {
            "entity": self.entity,
            "metric": self.metric,
            "period": self.period,
            "scope": self.scope,
            "unit": self.unit,
            "scale": self.scale,
        }

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> "FactKey":
        return cls(**{k: d[k] for k in
                      ("entity", "metric", "period", "scope", "unit", "scale")})

    def __str__(self) -> str:
        return (f"{self.entity} · {self.metric} · {self.period} · "
                f"{self.scope} ({self.unit} {self.scale})")


@dataclass(frozen=True)
class Observation:
    """One document's statement of a fact, with the evidence for it."""

    doc_id: str
    page: int
    bbox: tuple[float, float, float, float]   # PDF points, origin bottom-left
    quote: str
    channel: str
    value: int
    extraction: str = "layout"

    def __post_init__(self) -> None:
        if self.channel not in CHANNELS:
            raise ValueError(f"unknown channel {self.channel!r}")
        if self.extraction not in EXTRACTIONS:
            raise ValueError(f"unknown extraction {self.extraction!r}")
        if not self.quote.strip():
            raise ValueError("observation without a quote is not evidence")
        x0, y0, x1, y1 = self.bbox
        if not (x0 < x1 and y0 < y1):
            raise ValueError(f"degenerate bbox {self.bbox!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "page": self.page,
            "bbox": list(self.bbox),
            "quote": self.quote,
            "channel": self.channel,
            "value": self.value,
            "extraction": self.extraction,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Observation":
        return cls(
            doc_id=d["doc_id"],
            page=d["page"],
            bbox=tuple(d["bbox"]),  # type: ignore[arg-type]
            quote=d["quote"],
            channel=d["channel"],
            value=d["value"],
            extraction=d.get("extraction", "layout"),
        )


@dataclass
class Fact:
    """A claim, plus every observation of it in the corpus."""

    key: FactKey
    observations: list[Observation] = field(default_factory=list)

    @property
    def values(self) -> set[int]:
        return {o.value for o in self.observations}

    @property
    def agrees(self) -> bool:
        """True when every observation states the same value."""
        return len(self.values) <= 1

    @property
    def value(self) -> int | None:
        """The agreed value, or None when the sources disagree."""
        return next(iter(self.values)) if self.agrees and self.observations else None

    def channels(self) -> set[str]:
        return {o.channel for o in self.observations}

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.as_dict(),
            "observations": [o.as_dict() for o in self.observations],
        }
