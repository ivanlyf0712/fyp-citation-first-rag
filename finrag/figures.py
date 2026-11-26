"""Figures: link them to their description, store a crop, and read them once.

A figure is pixels, not text. Two consequences:

* a citation to a figure must carry the image, because there is no quote to check;
* the numbers inside it must be extracted once and stored, or nothing can verify
  an answer that comes from a chart.

Linking follows docs/VISUAL_SPEC.md: explicit reference, then nearest text block,
then section heading. The rule that fired is recorded so a citation can say how
confident the link is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REFERENCE = re.compile(
    r"(figure|fig\.?|chart|graph|diagram|exhibit)\s*\d+| as shown |shown below|"
    r"the chart|the figure|the diagram", re.I)

CHART_TYPES = {"bar", "line", "pie", "donut", "area", "scatter", "table-like",
               "photo", "logo", "unreadable"}


@dataclass
class FigureLink:
    figure_id: str
    text_id: str | None
    rule: str            # "explicit" | "nearest" | "heading" | "none"
    distance: float | None = None


def _vertical_gap(a, b) -> float:
    """Gap between two boxes; 0 if they overlap vertically."""
    if a[1] <= b[3] and b[1] <= a[3]:
        return 0.0
    return min(abs(a[3] - b[1]), abs(b[3] - a[1]))


def link_figures(units: list) -> list[FigureLink]:
    """For each figure, the text unit that describes it."""
    by_page: dict[tuple, list] = {}
    for unit in units:
        by_page.setdefault((unit.doc, unit.page), []).append(unit)

    links: list[FigureLink] = []
    for page_units in by_page.values():
        texts = [u for u in page_units if u.channel == "text"]
        for figure in (u for u in page_units if u.channel == "figure"):
            # 1. explicit reference
            referenced = [t for t in texts if REFERENCE.search(t.quote or "")]
            if referenced:
                best = min(referenced, key=lambda t: _vertical_gap(figure.bbox, t.bbox))
                links.append(FigureLink(figure.unit_id, best.unit_id, "explicit",
                                        _vertical_gap(figure.bbox, best.bbox)))
                continue
            # 2. nearest text block
            if texts:
                best = min(texts, key=lambda t: _vertical_gap(figure.bbox, t.bbox))
                links.append(FigureLink(figure.unit_id, best.unit_id, "nearest",
                                        _vertical_gap(figure.bbox, best.bbox)))
                continue
            links.append(FigureLink(figure.unit_id, None, "none"))
    return links


def chart_candidates(units: list, min_width: float = 180, min_height: float = 100,
                     max_height_ratio: float = 0.9) -> list:
    """Large, non-page-sized regions — a shortlist for the vision pass."""
    out = []
    for unit in units:
        if unit.channel != "figure":
            continue
        left, bottom, right, top = unit.bbox
        width, height = right - left, top - bottom
        if width >= min_width and height >= min_height:
            out.append(unit)
    return out


def store_crop(pdf_path: Path, unit, out_dir: Path, dpi: int = 140) -> Path:
    """Save the figure's region as an image; the citation points at this file."""
    from .ui import crop_region

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"p{unit.page}_{unit.unit_id.split(':')[-1][:10]}.png"
    if not dest.exists():
        crop_region(pdf_path.parent, pdf_path.name, unit.page, unit.bbox,
                    dpi=dpi, pad=0).save(dest)
    return dest
