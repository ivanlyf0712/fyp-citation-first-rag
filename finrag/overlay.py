"""Draw the parsed units back onto the page.

This is the check that matters before any annotation: *what did the parser
decide is evidence, and where does it think it is?* A box that floats off the
figure, or that covers a footnote instead of a number, is a parser error you can
only see by looking.

Coordinates: units store PDF coordinates with the origin bottom-left (the same
convention as the corpus). A rendered pixmap uses top-left, so y is mirrored
against the page height and then scaled by dpi/72.
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

#: channel -> RGB, chosen to stay legible over both white pages and images
COLOURS = {
    "text": (30, 90, 200),
    "table": (20, 140, 70),
    "figure": (200, 110, 20),
}

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def _font(size: int = 13):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def overlay_page(pdf_path: Path, page: int, units, accepted: set[str] | None = None,
                 dpi: int = 110, label_mode: str = "nontext",
                 only_numeric: bool = False,
                 highlight: str | None = None) -> Image.Image:
    """label_mode: "all" | "nontext" (tables and figures only) | "none"."""
    """Render one page with every unit's bbox drawn on it."""
    accepted = accepted or set()
    with pymupdf.open(pdf_path) as doc:
        pdf_page = doc[page - 1]
        height = pdf_page.rect.height
        pix = pdf_page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

    scale = dpi / 72.0
    draw = ImageDraw.Draw(img, "RGBA")
    font = _font()

    for unit in units:
        if unit.page != page:
            continue
        if only_numeric and not getattr(unit, "numbers", ()):
            continue
        x0, y0, x1, y1 = unit.bbox
        left, right = x0 * scale, x1 * scale
        top, bottom = (height - y1) * scale, (height - y0) * scale
        colour = COLOURS.get(unit.channel, (120, 120, 120))
        width = 3 if unit.unit_id in accepted else 2
        draw.rectangle([left, top, right, bottom],
                       outline=colour + (255,), width=width,
                       fill=colour + (26,))
        is_row = getattr(unit, "source", "") == "docling-row"
        wants = label_mode == "all" or (label_mode == "nontext" and unit.channel != "text")
        if wants and not is_row:
            tag = f"{unit.channel[0]}:{unit.unit_id[-4:]}"
            draw.rectangle([left, max(0, top - 15), left + 7 * len(tag), max(12, top - 1)],
                           fill=colour + (230,))
            draw.text((left + 2, max(0, top - 14)), tag, fill=(255, 255, 255), font=font)

    # the selected unit is drawn last, in a colour nothing else uses, so a click
    # is visible on the page rather than only in the side panel
    if highlight:
        for unit in units:
            if unit.unit_id != highlight or unit.page != page:
                continue
            x0, y0, x1, y1 = unit.bbox
            left, right = x0 * scale, x1 * scale
            top, bottom = (height - y1) * scale, (height - y0) * scale
            draw.rectangle([left, top, right, bottom],
                           outline=(220, 20, 60, 255), width=4,
                           fill=(220, 20, 60, 55))

    return img


def units_by_page(units) -> dict[int, list]:
    out: dict[int, list] = {}
    for unit in units:
        out.setdefault(unit.page, []).append(unit)
    return dict(sorted(out.items()))
