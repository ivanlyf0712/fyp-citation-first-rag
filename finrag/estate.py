"""The synthetic risk estate.

This module reproduces the generator in ``3-Working/baseline/baseline.py``
exactly — same seed, same distributions, same ordering — so that any figure
this package reports can be compared against the earlier baseline. The equality
is asserted in ``tests/test_estate.py``: if the two ever drift, the build fails
rather than quietly reporting different numbers.

Three things were added for the multimodal pipeline, and nothing was changed:

* documents are grouped into *cells* (counterparty × entity × desk) with an
  explicit identity, so facts can name the partition they describe;
* every cell and every counterparty carries the period, unit and scale that
  the reader will need to compare values;
* roles are named in one place, since permissions are inherited from documents
  and must be the same set everywhere.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass

SEED = 20261022
N_POSITIONS = 320

# Counterparty names are chosen so that no token collides with an entity or desk
# value; otherwise a generic retrieval matches on the shared word and the
# measurement confounds retrieval quality with permissions. (Same reasoning as
# the baseline, kept deliberately.)
COUNTERPARTIES = [
    "Harbour Finance",
    "Kowloon Commerce",
    "Meridian Bank",
    "Pacific Credits",
    "Tai Po Holdings",
    "Victoria Capital",
]
ENTITIES = ["HK", "SG", "JP"]
DESKS = ["trading", "credit", "treasury"]

PERIOD = "FY2024"
UNIT = "HKD"
SCALE = "million"

#: Metric names used in fact keys.
CELL_METRIC = "cell_exposure"
GROUP_METRIC = "group_total"

#: Counterparties whose consolidated total is stated in prose on the group
#: statement. The others disclose the total only inside a chart, so the text
#: channel cannot produce it at all.
TEXT_TOTAL_COUNTERPARTIES = {"Harbour Finance", "Kowloon Commerce", "Tai Po Holdings"}

#: The counterparty whose chart was rendered from a stale value. The text layer
#: says 817; the chart says 821. This is the `contradicts` case and it is
#: deliberate — a restated figure is the most common real cross-modal error.
STALE_CHART_COUNTERPARTY = "Harbour Finance"
STALE_CHART_DELTA = 4

#: Roles, as predicates over document metadata. These are the baseline's
#: predicates verbatim; they are data here rather than lambdas only so that the
#: same table can be printed and tested.
ROLE_RULES: dict[str, str] = {
    "Desk analyst (HK trading)": "entity == HK and desk == trading",
    "Treasury analyst": "desk == treasury",
    "Credit head": "desk == credit",
    "Regional head (Asia)": "entity in (HK, SG)",
    "Group CRO": "all",
    "Regulator (consolidated)": "all",
}

ROLE_NAMES = list(ROLE_RULES)


@dataclass(frozen=True)
class Position:
    pid: str
    counterparty: str
    entity: str
    desk: str
    notional_m: int


@dataclass(frozen=True)
class Cell:
    """One counterparty × entity × desk bucket: the unit of disclosure."""

    counterparty: str
    entity: str
    desk: str
    positions: tuple[Position, ...]

    @property
    def scope(self) -> str:
        return f"{self.entity}/{self.desk}"

    @property
    def total(self) -> int:
        return sum(p.notional_m for p in self.positions)


def build_positions(seed: int = SEED, n: int = N_POSITIONS) -> list[Position]:
    """Generate positions from a fixed seed. Same seed -> same estate, always."""
    rng = random.Random(seed)
    return [
        Position(
            pid=f"P-{i + 1:04d}",
            counterparty=rng.choice(COUNTERPARTIES),
            entity=rng.choice(ENTITIES),
            desk=rng.choice(DESKS),
            notional_m=int(round(rng.lognormvariate(2.4, 0.7))),
        )
        for i in range(n)
    ]


def build_cells(positions: list[Position]) -> list[Cell]:
    """Group positions into cells, ordered as the baseline orders its memos."""
    buckets: dict[tuple[str, str, str], list[Position]] = defaultdict(list)
    for p in positions:
        buckets[(p.counterparty, p.entity, p.desk)].append(p)
    return [
        Cell(counterparty=cp, entity=ent, desk=desk, positions=tuple(ps))
        for (cp, ent, desk), ps in sorted(buckets.items())
    ]


def gold_totals(positions: list[Position]) -> dict[str, int]:
    """Ground truth: firm-wide total per counterparty, by summation."""
    totals: dict[str, int] = defaultdict(int)
    for p in positions:
        totals[p.counterparty] += p.notional_m
    return dict(totals)


def role_permits(role: str, meta: dict[str, str]) -> bool:
    """Apply the role's predicate to a document's metadata.

    Mirrors the baseline's lambdas exactly, including the treatment of policy
    documents (``desk == "*"``), which only the regional head and the two
    unrestricted roles can read.
    """
    entity = meta.get("entity", "")
    desk = meta.get("desk", "")
    if role == "Desk analyst (HK trading)":
        return entity == "HK" and desk == "trading"
    if role == "Treasury analyst":
        return desk == "treasury"
    if role == "Credit head":
        return desk == "credit"
    if role == "Regional head (Asia)":
        return entity in ("HK", "SG")
    if role in ("Group CRO", "Regulator (consolidated)"):
        return True
    raise KeyError(f"unknown role {role!r}")


def acl_for(meta: dict[str, str]) -> frozenset[str]:
    """The set of roles permitted to read a document with these metadata."""
    return frozenset(r for r in ROLE_NAMES if role_permits(r, meta))


# --------------------------------------------------------------------------
# An irregular permission model, for the robustness experiment
# --------------------------------------------------------------------------
#: The strict model grants access by a predicate over (entity, desk), so each
#: role's visible set is a rectangle. Real access control is not rectangular:
#: documents are shared with groups, and individual documents carry exceptions.
#: This variant adds both, deterministically, so the same document always gets
#: the same treatment.
def irregular_acl(meta: dict[str, str], doc_id: str) -> frozenset[str]:
    """Strict ACL plus a deterministic grant and a deterministic denial."""
    base = set(acl_for(meta))
    h = int(hashlib.sha256(doc_id.encode()).hexdigest(), 16)

    # roughly 1 document in 11 is shared beyond its cell with the regional lead
    if h % 11 == 0:
        base.add("Regional head (Asia)")

    # roughly 1 in 7 loses a role that the predicate would have granted
    if h % 7 == 0:
        removable = sorted(base - {"Group CRO", "Regulator (consolidated)"})
        if len(removable) > 1:
            base.discard(removable[h % len(removable)])

    return frozenset(base)
