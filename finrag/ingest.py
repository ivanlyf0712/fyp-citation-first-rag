"""Parse a real PDF into citeable units, with a human in the loop.

Division of labour:

* **Docling** decides *what* a region is — text block, table, figure — and where
  the region sits. It is a layout model, not a coordinate authority.
* **The PDF text layer** decides *where the glyphs are*. `get_text("words")`
  returns exact word boxes from the file, with no recognition error and no
  second model. Text units are rebuilt per **line** inside Docling's text
  regions, and every box is snapped to the union of its words, so a heading and
  its numbering share one unit and no box floats off its ink.
* **OCR** is reserved for pages that have no text layer at all. Those pages are
  flagged rather than silently approximated.

Coordinates are stored in PDF convention (origin bottom-left), which is what the
corpus, the cropper and Docling's own region boxes use. PyMuPDF reports
top-left, so words are mirrored against the page height on the way in.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

NUMBER = re.compile(r"[-−(]?\d[\d,]*(?:\.\d+)?\)?")

#: Bump when unit construction changes; old caches are then ignored rather than
#: silently reused with different semantics.
CACHE_VERSION = 4

#: Page-height fractions treated as running header / footer. **Disabled by
#: default, deliberately.** Measured on three filings (VALIDATION.md): the band
#: removed 4 units from the bank report but 37 of 49 from an ESG report, four of
#: them containing figures. A position threshold tuned on one layout is not a
#: rule; detecting repeated lines across pages is the robust version, and is not
#: implemented yet.
PAGE_TOP_BAND = 0.095
PAGE_BOTTOM_BAND = 0.060


@dataclass(frozen=True)
class DraftUnit:
    unit_id: str
    doc: str
    page: int
    bbox: tuple[float, float, float, float]
    quote: str
    channel: str                  # text | table | figure
    value: float | None
    numbers: tuple[float, ...]    # every number found in the quote
    value_flag: str               # "" | "no number" | "multiple numbers" | ...
    source: str = "text-layer"    # text-layer | docling | ocr
    extractor: str = "docling"

    def as_dict(self) -> dict:
        return {
            "unit_id": self.unit_id, "doc": self.doc, "page": self.page,
            "bbox": list(self.bbox), "quote": self.quote, "channel": self.channel,
            "value": self.value, "numbers": list(self.numbers),
            "value_flag": self.value_flag, "source": self.source,
            "extractor": self.extractor,
        }


# --------------------------------------------------------------------------
# numbers
# --------------------------------------------------------------------------
def parse_numbers(text: str) -> tuple[list[float], str]:
    """Every number in the span, and why the value may be unusable.

    Parentheses mark negatives in financial statements — `(2,103,519)` is minus
    two million — so they are read as a sign rather than stripped.
    """
    found = NUMBER.findall(text)
    values: list[float] = []
    for raw in found:
        negative = raw.startswith("(") or raw.startswith("−") or raw.startswith("-")
        cleaned = raw.strip("()−-").replace(",", "")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        values.append(-value if negative else value)
    if not values:
        return [], "no number"
    if len(values) == 1:
        return values, ""
    return values, "multiple numbers"


# --------------------------------------------------------------------------
# words and lines
# --------------------------------------------------------------------------
def _words(pdf_page: pymupdf.Page) -> list[dict]:
    """Word boxes in PDF coordinates (bottom-left origin)."""
    height = pdf_page.rect.height
    out = []
    for x0, y0, x1, y1, text, block, line, _word in pdf_page.get_text("words"):
        if not text.strip():
            continue
        out.append({"x0": x0, "y0": height - y1, "x1": x1, "y1": height - y0,
                    "text": text, "block": block, "line": line})
    return out


def _inside(word: dict, bbox, tol: float = 2.0) -> bool:
    cx = (word["x0"] + word["x1"]) / 2
    cy = (word["y0"] + word["y1"]) / 2
    l, b, r, t = bbox
    return (l - tol) <= cx <= (r + tol) and (b - tol) <= cy <= (t + tol)


def _union(words: list[dict]) -> tuple[float, float, float, float]:
    return (min(w["x0"] for w in words), min(w["y0"] for w in words),
            max(w["x1"] for w in words), max(w["y1"] for w in words))


def _by_block(words: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for word in words:
        out.setdefault(word["block"], []).append(word)
    return out


def _lines(words: list[dict]) -> list[list[dict]]:
    grouped: dict[tuple[int, int], list[dict]] = {}
    for word in words:
        grouped.setdefault((word["block"], word["line"]), []).append(word)
    lines = [sorted(ws, key=lambda w: w["x0"]) for ws in grouped.values()]
    return sorted(lines, key=lambda ws: (-max(w["y1"] for w in ws),
                                          min(w["x0"] for w in ws)))


def _make_unit(name: str, page: int, channel: str, bbox, quote: str,
               source: str) -> DraftUnit:
    numbers, flag = parse_numbers(quote)
    value = numbers[0] if len(numbers) == 1 else None
    if channel == "figure":
        flag = "figure: needs a vision model"
    uid = "U:" + hashlib.sha1(
        f"{name}|{page}|{channel}|{tuple(round(v, 1) for v in bbox)}|{quote[:80]}".encode()
    ).hexdigest()[:10]
    return DraftUnit(unit_id=uid, doc=name, page=page,
                     bbox=tuple(round(v, 2) for v in bbox), quote=quote,
                     channel=channel, value=value, numbers=tuple(numbers),
                     value_flag=flag, source=source)


# --------------------------------------------------------------------------
# page assembly
# --------------------------------------------------------------------------

def _same_visual_line(a, b, overlap: float = 0.5) -> bool:
    """Do two boxes sit on the same baseline?"""
    top = min(a[3], b[3])
    bottom = max(a[1], b[1])
    if top <= bottom:
        return False
    height = min(a[3] - a[1], b[3] - b[1]) or 1.0
    return (top - bottom) / height >= overlap


def _horizontal_gap(a, b) -> float:
    if b[0] >= a[2]:
        return b[0] - a[2]
    if a[0] >= b[2]:
        return a[0] - b[2]
    return 0.0


_ENUM = re.compile(r"^(?:[IVXLC]+\.?|\(?[ivxlc]+\)?|\d+\.|\([A-Za-z0-9]{1,3}\))$")


def _is_enumerator(text: str) -> bool:
    """A bare label: "V.", "(I)", "1.", "(a)" — but not a page number like "17"."""
    return bool(_ENUM.match(text.strip()))


def _merge_numbering(units: list[DraftUnit], name: str, page: int) -> list[DraftUnit]:
    """Rejoin a bare enumerator ("V.", "(I)", "1.") to the heading beside it.

    Docling and PyMuPDF both split a large enumerator from the heading it labels,
    because they are different font sizes. The rule is deliberately narrow: same
    visual line, almost touching, and one side is at most six characters — which
    joins "V." to "ANALYSIS OF FINANCIAL STATEMENTS" without gluing a page header
    to a page number.
    """
    ordered = sorted(units, key=lambda u: (-u.bbox[3], u.bbox[0]))
    merged: list[DraftUnit] = []
    for unit in ordered:
        target = None
        for i, other in enumerate(merged):
            if not _same_visual_line(other.bbox, unit.bbox):
                continue
            if _horizontal_gap(other.bbox, unit.bbox) > 10:
                continue
            if _is_enumerator(other.quote) or _is_enumerator(unit.quote):
                target = i
                break
        if target is None:
            merged.append(unit)
            continue
        other = merged[target]
        left, right = (other, unit) if other.bbox[0] <= unit.bbox[0] else (unit, other)
        bbox = (min(left.bbox[0], right.bbox[0]), min(left.bbox[1], right.bbox[1]),
                max(left.bbox[2], right.bbox[2]), max(left.bbox[3], right.bbox[3]))
        merged[target] = _make_unit(name, page, "text", bbox,
                                    f"{left.quote} {right.quote}", "text-layer")
    return sorted(merged, key=lambda u: (-u.bbox[3], u.bbox[0]))

def _region_bbox(prov) -> tuple[float, float, float, float]:
    b = prov.bbox
    return (float(b.l), float(b.b), float(b.r), float(b.t))


def _units_from_page(doc, pdf_page: pymupdf.Page, name: str,
                     margins: bool = True) -> list[DraftUnit]:
    """Docling regions + text-layer lines -> units for one page."""
    page_no = pdf_page.number + 1
    height = pdf_page.rect.height
    words = _words(pdf_page)
    units: list[DraftUnit] = []

    # text: rebuild per line inside each Docling text region
    emitted: set[tuple[int, int]] = set()
    for item in getattr(doc, "texts", []):
        if not item.prov:
            continue
        prov = item.prov[0]
        if prov.page_no != page_no:
            continue
        region = _region_bbox(prov)
        inside = [w for w in words if _inside(w, region)]
        # one unit per paragraph block, not per line: a sentence that wraps must
        # not be split away from the number it carries ("RMB25,482" / "million")
        for block_id, block_words in _by_block(inside).items():
            lines = _lines(block_words)
            quote = " ".join(" ".join(w["text"] for w in line) for line in lines).strip()
            keys = {(line[0]["block"], line[0]["line"]) for line in lines}
            if not quote or keys & emitted:
                continue
            emitted |= keys
            units.append(_make_unit(name, page_no, "text",
                                    _union([w for line in lines for w in line]),
                                    quote, "text-layer"))
        if not inside:                      # text baked into an image
            text = (item.text or "").strip()
            if text:
                units.append(_make_unit(name, page_no, "text", region, text, "docling"))

    # Regions that are not text: their words must not become text units, or
    # every table cell would be cited as a sentence.
    non_text_regions = []
    for kind in ("tables", "pictures"):
        for item in getattr(doc, kind, []):
            if item.prov and item.prov[0].page_no == page_no:
                non_text_regions.append(_region_bbox(item.prov[0]))

    def in_non_text(word) -> bool:
        return any(_inside(word, r) for r in non_text_regions)

    # any line of the page not claimed by a Docling region (footers, columns)
    leftover = [w for w in words
                if (w["block"], w["line"]) not in emitted and not in_non_text(w)]
    for block_id, block_words in _by_block(leftover).items():
        lines = _lines(block_words)
        quote = " ".join(" ".join(w["text"] for w in line) for line in lines).strip()
        if quote:
            units.append(_make_unit(name, page_no, "text",
                                    _union([w for line in lines for w in line]),
                                    quote, "text-layer"))

    # tables: one unit per row, so a citation points at "Net profit | 5,255,815"
    # rather than at the whole statement
    for item in getattr(doc, "tables", []):
        if not item.prov:
            continue
        prov = item.prov[0]
        if prov.page_no != page_no:
            continue
        region = _region_bbox(prov)

        rows: dict[int, list] = {}
        for cell in getattr(item.data, "table_cells", []) or []:
            text = (cell.text or "").strip()
            if not text:
                continue
            rows.setdefault(cell.start_row_offset_idx, []).append(cell)

        if rows:
            ordered = {idx: sorted(rows[idx], key=lambda c: c.bbox.l) for idx in sorted(rows)}
            header_row = ordered[min(ordered)] if len(ordered) > 1 else []
            for idx in sorted(ordered):
                cells = ordered[idx]
                boxes = []
                for cell in cells:
                    b = cell.bbox
                    # cells are reported TOPLEFT; the rest of the code is bottom-left
                    boxes.append((float(b.l), height - float(b.b),
                                  float(b.r), height - float(b.t)))
                bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                        max(b[2] for b in boxes), max(b[3] for b in boxes))
                quote = " | ".join((c.text or "").strip() for c in cells)
                units.append(_make_unit(name, page_no, "table", bbox, quote,
                                        "docling-row"))

                # one unit per data cell: "2024 · Net profit: 5,255,815". A row
                # quote holds every year, so citing it cannot tell 2024 from 2023
                # — the cell can.
                if idx == min(ordered):
                    continue                      # the header is not evidence
                label = (cells[0].text or "").strip()
                if not label or parse_numbers(label)[0]:
                    continue                      # unlabelled or numeric-first row
                for column, cell in enumerate(cells[1:], start=1):
                    text = (cell.text or "").strip()
                    if not text or parse_numbers(text)[0] == []:
                        continue
                    # the header row has no label cell of its own, so its
                    # column j sits above the row's cell j+1
                    head_index = (column - 1 if len(header_row) == len(cells) - 1
                                  else column)
                    year = ((header_row[head_index].text or "").strip()
                            if 0 <= head_index < len(header_row) else "")
                    year = year[:24]
                    b = cell.bbox
                    unit_quote = (f"{year} · {label}: {text}" if year
                                  else f"{label}: {text}")
                    units.append(_make_unit(
                        name, page_no, "cell",
                        (float(b.l), height - float(b.b), float(b.r),
                         height - float(b.t)),
                        unit_quote, "docling-cell"))
        else:
            try:
                frame = item.export_to_dataframe(doc=doc)
                quote = " | ".join(str(c) for c in frame.iloc[0].tolist())
            except Exception:
                quote = "[table]"
            units.append(_make_unit(name, page_no, "table", region,
                                    quote.strip() or "[table]", "docling"))

    # drop running headers and footers
    low, high = PAGE_BOTTOM_BAND * height, height - PAGE_TOP_BAND * height

    def in_body(unit: DraftUnit) -> bool:
        centre = (unit.bbox[1] + unit.bbox[3]) / 2
        return low <= centre <= high

    if margins:
        units = [u for u in units if u.channel != "text" or in_body(u)]

    # rejoin numbering that the parser split from its heading
    text_units = _merge_numbering([u for u in units if u.channel == "text"],
                                  name, page_no)
    units = text_units + [u for u in units if u.channel != "text"]

    # figures
    for item in getattr(doc, "pictures", []):
        if not item.prov:
            continue
        prov = item.prov[0]
        if prov.page_no != page_no:
            continue
        caption = ""
        for ref in getattr(item, "captions", []) or []:
            caption += getattr(ref, "text", "") or ""
        units.append(_make_unit(name, page_no, "figure", _region_bbox(prov),
                                (caption.strip() or "[figure]")[:400], "docling"))

    return units


def page_has_text(pdf_page: pymupdf.Page) -> bool:
    return bool(pdf_page.get_text("text").strip())


def parse_pdf(path: Path, start: int = 1, end: int = 20,
              progress=None, margins: bool = False) -> list[DraftUnit]:
    """Parse pages ``start..end`` into draft units, reporting progress per page."""
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    units: list[DraftUnit] = []
    total = max(end - start + 1, 1)

    with pymupdf.open(path) as pdf:
        for offset, page_no in enumerate(range(start, end + 1)):
            pdf_page = pdf[page_no - 1]
            if not page_has_text(pdf_page):
                # No text layer: flagged, not silently approximated. OCR is the
                # next step for these pages.
                units.append(_make_unit(path.name, page_no, "text",
                                        (0, 0, pdf_page.rect.width, pdf_page.rect.height),
                                        "[page has no text layer: OCR required]",
                                        "ocr"))
            else:
                try:
                    result = converter.convert(str(path), page_range=(page_no, page_no))
                    units.extend(_units_from_page(result.document, pdf_page, path.name,
                                                  margins=margins))
                except Exception:
                    pass
            if progress:
                progress(offset + 1, total)
    return units


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------
def save_cache(cache_dir: Path, pdf: Path, units: list[DraftUnit],
               start: int = 1, end: int | None = None) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    end = end or max((u.page for u in units), default=start)
    out = cache_dir / f"{pdf.stem}.p{start}-{end}.v{CACHE_VERSION}.units.json"
    out.write_text(json.dumps([u.as_dict() for u in units], indent=2) + "\n")
    return out


def load_cache(cache_dir: Path, pdf: Path, start: int = 1,
               end: int | None = None) -> list[DraftUnit] | None:
    end = end or start
    path = cache_dir / f"{pdf.stem}.p{start}-{end}.v{CACHE_VERSION}.units.json"
    if not path.exists():
        return None
    out = []
    for row in json.loads(path.read_text()):
        row.setdefault("numbers", [])
        row.setdefault("source", "text-layer")
        row["bbox"] = tuple(row["bbox"])
        row["numbers"] = tuple(row.get("numbers") or ())
        out.append(DraftUnit(**row))
    return out


def parse_pages(path: Path, pages: list[int], progress=None):
    """Parse an explicit list of pages with one loaded model.

    Returns (units, stats). Each page is attempted independently: a failure is
    recorded and parsing continues, because a smoke test over a whole report
    must report the bad pages rather than stop at the first one.
    """
    import time as _time

    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    units: list[DraftUnit] = []
    stats: list[dict] = []

    with pymupdf.open(path) as pdf:
        for page_no in pages:
            started = _time.perf_counter()
            entry = {"page": page_no, "units": 0, "rows": 0, "tables": 0,
                     "numeric": 0, "seconds": 0.0, "error": None, "blank": False}
            pdf_page = pdf[page_no - 1]
            if not page_has_text(pdf_page):
                entry["blank"] = True
            else:
                try:
                    result = converter.convert(str(path), page_range=(page_no, page_no))
                    page_units = _units_from_page(result.document, pdf_page, path.name)
                    units.extend(page_units)
                    entry["units"] = len(page_units)
                    entry["rows"] = sum(1 for u in page_units if u.source == "docling-row")
                    entry["tables"] = sum(1 for u in page_units if u.channel == "table")
                    entry["numeric"] = sum(1 for u in page_units if u.numbers)
                except Exception as exc:                       # noqa: BLE001
                    entry["error"] = f"{type(exc).__name__}: {exc}"[:200]
            entry["seconds"] = round(_time.perf_counter() - started, 1)
            stats.append(entry)
            if progress:
                progress(page_no, entry)
    return units, stats
