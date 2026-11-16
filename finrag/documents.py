"""Render the corpus to PDF and record exact ground truth.

Design commitments (see docs/SPEC.md §3, §6, §8):

* Every number that is meant to be readable is drawn as a *single line* of text
  whose width is measured, so its bounding box is exact rather than estimated.
* Charts are rasterised to PNG and embedded as images. Their labels are pixels,
  so a text extraction of a figure page cannot recover them. That is what makes
  the visual channel genuinely visual.
* Ground truth is recorded while drawing (the *perfect extraction* condition).
  It is labelled `extraction="layout"` on every observation, and the text layer
  is independently verified afterwards by `verify_text_layer`, which re-opens
  each PDF and checks that every text fact really is present in the page text
  and that no figure-only value is.

The document shapes follow the evidence graph literature's treatment of
financial filings as typed units (HC-RAG, arXiv:2608.12335: document, section,
text unit, table unit); we add a figure unit because the chart is where this
project's cross-modal case lives.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pymupdf
from PIL import Image, ImageDraw, ImageFont
from reportlab import rl_config
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

from .estate import (
    CELL_METRIC,
    ENTITIES,
    GROUP_METRIC,
    PERIOD,
    SCALE,
    SEED,
    STALE_CHART_COUNTERPARTY,
    STALE_CHART_DELTA,
    TEXT_TOTAL_COUNTERPARTIES,
    UNIT,
    Cell,
    acl_for,
    build_cells,
    build_positions,
)
from .facts import Fact, FactKey, Observation

# Invariant output: no creation timestamp, no random document ID. Without this
# two builds of the same corpus differ at the byte level and NFR1 is false.
rl_config.invariant = 1

W, H = A4
MARGIN = 56.0
BODY = 11.0
LEADING = 16.0
FIG_W, FIG_H = 480.0, 336.0

INK = HexColor("#111111")
MUTED = HexColor("#666666")
RULE = HexColor("#BBBBBB")

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


# --------------------------------------------------------------------------
# Rendering primitives
# --------------------------------------------------------------------------
class Writer:
    """A page under construction: keeps the cursor, records text boxes."""

    def __init__(self, canvas: pdfcanvas.Canvas, doc_id: str, page: int) -> None:
        self.c = canvas
        self.doc_id = doc_id
        self.page = page
        self.y = H - MARGIN
        self.boxes: list[tuple[float, float, float, float]] = []
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN, self.y, f"{doc_id} · page {page}")
        self.y -= 26

    def line(self, text: str, size: float = BODY, bold: bool = False,
             colour: HexColor = INK, leading: float = LEADING,
             indent: float = 0.0) -> tuple[float, float, float, float]:
        """Draw one line and return its bbox in PDF points."""
        font = "Helvetica-Bold" if bold else "Helvetica"
        width = stringWidth(text, font, size)
        limit = W - 2 * MARGIN - indent
        if width > limit:
            raise ValueError(
                f"{text[:40]!r} is {width:.0f}pt wide, limit {limit:.0f}pt; "
                "split it rather than letting it overflow"
            )
        x = MARGIN + indent
        self.c.setFillColor(colour)
        self.c.setFont(font, size)
        self.c.drawString(x, self.y, text)
        box = (x, self.y - 3.0, x + width, self.y + size)
        self.boxes.append(box)
        self.y -= leading
        return box

    def gap(self, amount: float = 8.0) -> None:
        self.y -= amount


def _figure_png(path: Path, title: str, labels: list[str], values: list[int],
                total_label: str | None, total_value: int | None,
                footnote: str) -> None:
    """Draw a bar chart to PNG. Every glyph here becomes a pixel.

    The annotation above the highlighted bar is the only place the total value
    exists in this file, which is what makes it figure-only evidence.
    """
    img_w, img_h = 1000, 700
    img = Image.new("RGB", (img_w, img_h), "white")
    d = ImageDraw.Draw(img)

    font = font_t = None
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                font = ImageFont.truetype(candidate, 19)
                font_b = ImageFont.truetype(candidate, 22)
                font_t = ImageFont.truetype(candidate, 26)
                break
            except OSError:
                continue
    font = font or ImageFont.load_default()
    font_b = locals().get("font_b") or font
    font_t = font_t or font

    d.text((40, 24), title, fill=(20, 20, 20), font=font_t)
    left, right, top, bottom = 90, img_w - 40, 100, img_h - 170
    d.line([(left, bottom), (right, bottom)], fill=(80, 80, 80), width=2)
    d.line([(left, top), (left, bottom)], fill=(80, 80, 80), width=2)

    peak = max(values + ([total_value] if total_value is not None else [0])) or 1
    scale = (bottom - top) / (peak * 1.10)

    n = len(values) + (1 if total_value is not None else 0)
    slot = (right - left) / max(n, 1)
    bar_w = min(slot * 0.60, 64)

    def centred(text: str, cx: float, y: float, f, fill) -> None:
        width = d.textlength(text, font=f)
        d.text((cx - width / 2, y), text, fill=fill, font=f)

    for i, (label, value) in enumerate(zip(labels, values)):
        cx = left + i * slot + slot / 2
        y0 = bottom - value * scale
        d.rectangle([cx - bar_w / 2, y0, cx + bar_w / 2, bottom], fill=(90, 120, 160))
        centred(str(value), cx, y0 - 28, font, (30, 30, 30))
        for k, part in enumerate(label.split("/")):
            centred(part, cx, bottom + 12 + k * 24, font, (60, 60, 60))

    if total_value is not None:
        cx = left + len(values) * slot + slot / 2
        y0 = bottom - total_value * scale
        d.rectangle([cx - bar_w / 2, y0, cx + bar_w / 2, bottom], fill=(160, 80, 60))
        centred(str(total_value), cx, y0 - 32, font_b, (120, 30, 20))
        for k, part in enumerate((total_label or "total").split("/")):
            centred(part, cx, bottom + 12 + k * 24, font_b, (120, 30, 20))

    d.text((left, img_h - 52), footnote, fill=(90, 90, 90), font=font)
    img.save(path)


# --------------------------------------------------------------------------
# Corpus
# --------------------------------------------------------------------------
@dataclass
class DocRecord:
    doc_id: str
    kind: str
    path: str
    meta: dict[str, str]
    acl: list[str]
    pages: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "kind": self.kind,
            "path": self.path,
            "meta": self.meta,
            "acl": self.acl,
            "pages": self.pages,
        }


@dataclass
class Corpus:
    documents: list[DocRecord] = field(default_factory=list)
    facts: dict[FactKey, Fact] = field(default_factory=dict)

    def observe(self, key: FactKey, obs: Observation) -> None:
        self.facts.setdefault(key, Fact(key=key)).observations.append(obs)

    def digest(self) -> str:
        payload = {
            "documents": [d.as_dict() for d in self.documents],
            "facts": [f.as_dict() for _, f in sorted(self.facts.items())],
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "seed": SEED,
            "period": PERIOD,
            "documents": [d.as_dict() for d in self.documents],
            "facts": [f.as_dict() for _, f in sorted(self.facts.items())],
            "digest": self.digest(),
        }


def _memo_pages(c: pdfcanvas.Canvas, corpus: Corpus, doc_id: str,
                cell: Cell, acl: list[str], fig_dir: Path) -> int:
    cp, ent, desk = cell.counterparty, cell.entity, cell.desk
    key = FactKey(cp, CELL_METRIC, PERIOD, cell.scope, UNIT, SCALE)
    total = cell.total

    # ---- page 1: prose + table -------------------------------------------
    w = Writer(c, doc_id, 1)
    w.line(f"Credit memo — {cp}", size=17, bold=True, leading=24)
    w.line(f"{ent} entity · {desk} desk · period {PERIOD}", colour=MUTED, leading=20)
    w.gap(6)
    w.line(f"Credit memo. Counterparty {cp}, {ent} entity, {desk} desk.",
           leading=LEADING)
    sentence = f"Aggregate exposure for this cell is HK$ {total} million across {len(cell.positions)} positions."
    box = w.line(sentence)
    corpus.observe(key, Observation(doc_id, 1, box, sentence, "text", total))
    w.line("Exposure is stated gross of collateral and before netting.")

    # Table of positions, with a total row. Positions are shown for realism;
    # the fact extracted from the table is the cell aggregate, not each row.
    top = w.y - 12
    col_x = (MARGIN, MARGIN + 300)
    row_h = 15.0
    c.setStrokeColor(RULE)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(col_x[0], top, "Position")
    c.drawString(col_x[1], top, "Notional (HK$ m)")
    c.line(MARGIN, top - 4, W - MARGIN, top - 4)
    y = top - 18
    c.setFont("Helvetica", 9)
    for p in cell.positions:
        c.setFillColor(INK)
        c.drawString(col_x[0], y, p.pid)
        c.drawString(col_x[1], y, f"{p.notional_m}")
        y -= row_h
    c.setStrokeColor(INK)
    c.line(MARGIN, y + 8, W - MARGIN, y + 8)
    total_quote = f"Total {total}"
    c.setFont("Helvetica-Bold", 9)
    c.drawString(col_x[0], y - 4, "Total")
    c.drawString(col_x[1], y - 4, f"{total}")
    width = stringWidth(f"{total}", "Helvetica-Bold", 9)
    corpus.observe(key, Observation(
        doc_id, 1, (col_x[1], y - 7, col_x[1] + width, y + 6),
        total_quote, "table", total))
    c.showPage()

    # ---- page 2: figure ---------------------------------------------------
    w = Writer(c, doc_id, 2)
    w.line(f"{cp} — {ent} {desk} exposure by position", size=15, bold=True, leading=22)
    w.line("Figure 1. Position-level notionals for this cell.", colour=MUTED, leading=18)
    w.gap(8)
    fig_id = f"{doc_id}-F1"
    png = fig_dir / f"{fig_id}.png"
    labels = [p.pid.replace("P-", "") for p in cell.positions]
    values = [p.notional_m for p in cell.positions]
    _figure_png(png, f"{cp} · {ent} {desk} · {PERIOD}", labels, values,
                "cell total", total,
                "Position notionals in HKD million; the highlighted bar is the cell total.")
    y_img = w.y - FIG_H
    c.drawImage(ImageReader(str(png)), MARGIN, y_img, width=FIG_W, height=FIG_H,
                preserveAspectRatio=True, mask="auto")
    fbox = (MARGIN, y_img, MARGIN + FIG_W, y_img + FIG_H)
    quote = (f"Figure 1: {cp} {ent} {desk} exposure by position; "
             f"cell total {total} million.")
    corpus.observe(key, Observation(doc_id, 2, fbox, quote, "figure", total,
                                    extraction="oracle"))
    c.showPage()
    return 2


def _group_pages(c: pdfcanvas.Canvas, corpus: Corpus, doc_id: str,
                 cp: str, cells: list[Cell], total_value: int,
                 acl: list[str], fig_dir: Path) -> int:
    key = FactKey(cp, GROUP_METRIC, PERIOD, "group", UNIT, SCALE)
    text_total = cp in TEXT_TOTAL_COUNTERPARTIES
    chart_value = total_value + STALE_CHART_DELTA if cp == STALE_CHART_COUNTERPARTY else total_value

    # ---- page 1: prose ----------------------------------------------------
    w = Writer(c, doc_id, 1)
    w.line(f"Group exposure statement — {cp}", size=17, bold=True, leading=24)
    w.line(f"Consolidated · period {PERIOD}", colour=MUTED, leading=20)
    w.gap(6)
    w.line(f"Group exposure statement. Counterparty {cp}, period {PERIOD}.")
    if text_total:
        sentence = (f"Consolidated group exposure is HK$ {total_value} million "
                    f"across {len(cells)} disclosure cells.")
        box = w.line(sentence)
        corpus.observe(key, Observation(doc_id, 1, box, sentence, "text", total_value))
    else:
        w.line("Consolidated exposure is presented in Figure 1 and is not restated in this note.")
    w.line("Figures are stated in HKD million and are not audited.")

    # A small table of cell counts, to give the page a real text layer.
    w.gap(10)
    w.line("Disclosure cells in scope", bold=True, leading=18)
    for cell in cells:
        w.line(f"  {cell.scope}: {len(cell.positions)} positions", size=10, leading=13)
    c.showPage()

    # ---- page 2: figure ---------------------------------------------------
    w = Writer(c, doc_id, 2)
    w.line(f"{cp} — consolidated exposure by cell", size=15, bold=True, leading=22)
    w.line("Figure 1. Cell exposures and the consolidated total.", colour=MUTED, leading=18)
    w.gap(8)
    fig_id = f"{doc_id}-F1"
    png = fig_dir / f"{fig_id}.png"
    labels = [cell.scope for cell in cells]
    values = [cell.total for cell in cells]
    _figure_png(png, f"{cp} · consolidated {PERIOD}", labels, values,
                "group total", chart_value,
                "Cell exposures in HKD million; the highlighted bar is the consolidated total.")
    y_img = w.y - FIG_H
    c.drawImage(ImageReader(str(png)), MARGIN, y_img, width=FIG_W, height=FIG_H,
                preserveAspectRatio=True, mask="auto")
    fbox = (MARGIN, y_img, MARGIN + FIG_W, y_img + FIG_H)
    quote = f"Figure 1: {cp} consolidated exposure by cell; group total {chart_value} million."
    corpus.observe(key, Observation(doc_id, 2, fbox, quote, "figure", chart_value,
                                    extraction="oracle"))
    c.showPage()
    return 2


def _policy_pages(c: pdfcanvas.Canvas, doc_id: str, ent: str) -> int:
    w = Writer(c, doc_id, 1)
    w.line(f"Policy extract — {ent} entity", size=17, bold=True, leading=24)
    w.line(f"Aggregation policy · period {PERIOD}", colour=MUTED, leading=20)
    w.gap(6)
    w.line(f"Policy extract. Aggregation policy for the {ent} entity.")
    w.line("Exposure is aggregated by counterparty within each entity and desk.")
    w.line("Consolidation requires every contributing cell to be visible to the reader.")
    w.line("Where a contributing cell is not visible, the consolidated figure may not be derived.")
    w.line("Charts are prepared from the same position table as the tables in this pack.")
    c.showPage()
    return 1


def build_corpus(out_dir: Path, seed: int = SEED, acl_fn=None) -> Corpus:
    """Render every document and return the corpus with its ground truth."""
    out_dir = Path(out_dir)
    corpus_dir = out_dir / "corpus"
    fig_dir = out_dir / "corpus" / "figures"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    positions = build_positions(seed)
    cells = build_cells(positions)
    totals = {cp: sum(c.total for c in cells if c.counterparty == cp)
              for cp in sorted({c.counterparty for c in cells})}

    corpus = Corpus()
    by_cp: dict[str, list[Cell]] = {}
    for cell in cells:
        by_cp.setdefault(cell.counterparty, []).append(cell)

    # Credit memos, one per occupied cell.
    for i, cell in enumerate(cells, start=1):
        doc_id = f"D-{i:03d}"
        meta = {"counterparty": cell.counterparty, "entity": cell.entity,
                "desk": cell.desk, "period": PERIOD}
        acl = sorted((acl_fn or (lambda m, d: acl_for(m)))(meta, doc_id))
        path = corpus_dir / f"{doc_id}.pdf"
        c = pdfcanvas.Canvas(str(path), pagesize=A4)
        c.setTitle(f"Credit memo {cell.counterparty} {cell.entity} {cell.desk}")
        pages = _memo_pages(c, corpus, doc_id, cell, acl, fig_dir)
        c.save()
        corpus.documents.append(DocRecord(doc_id, "credit_memo", str(path.relative_to(out_dir)),
                                          meta, acl, pages))

    # Group statements, one per counterparty.
    for j, cp in enumerate(sorted(by_cp), start=1):
        doc_id = f"D-G{j:02d}"
        meta = {"counterparty": cp, "entity": "*", "desk": "*", "period": PERIOD}
        acl = sorted((acl_fn or (lambda m, d: acl_for(m)))(meta, doc_id))
        path = corpus_dir / f"{doc_id}.pdf"
        c = pdfcanvas.Canvas(str(path), pagesize=A4)
        c.setTitle(f"Group exposure statement {cp}")
        pages = _group_pages(c, corpus, doc_id, cp, by_cp[cp], totals[cp], acl, fig_dir)
        c.save()
        corpus.documents.append(DocRecord(doc_id, "group_statement", str(path.relative_to(out_dir)),
                                          meta, acl, pages))

    # Policy extracts, one per entity.
    for k, ent in enumerate(ENTITIES, start=1):
        doc_id = f"D-P{k:02d}"
        meta = {"counterparty": "", "entity": ent, "desk": "*", "period": PERIOD}
        acl = sorted((acl_fn or (lambda m, d: acl_for(m)))(meta, doc_id))
        path = corpus_dir / f"{doc_id}.pdf"
        c = pdfcanvas.Canvas(str(path), pagesize=A4)
        c.setTitle(f"Policy extract {ent}")
        pages = _policy_pages(c, doc_id, ent)
        c.save()
        corpus.documents.append(DocRecord(doc_id, "policy", str(path.relative_to(out_dir)),
                                          meta, acl, pages))

    return corpus


# --------------------------------------------------------------------------
# Verification: the ground truth must be true of the PDFs
# --------------------------------------------------------------------------

_NUMBER = re.compile(r"\d[\d,]*")


def _page_text(pdf: Path, page: int) -> str:
    with pymupdf.open(pdf) as doc:
        return doc[page - 1].get_text("text")


def verify_text_layer(corpus: Corpus, out_dir: Path) -> dict[str, Any]:
    """Re-open every PDF and check the ground truth against the real text layer.

    Two checks per page:

    * every observation made through `text` or `table` has its value present in
      the extracted text — the text channel really can see it;
    * every observation made through `figure` has its value absent from the
      extracted text, unless the same page also states it in text — the visual
      channel is really visual.

    Returns a report; raises `AssertionError` on any violation.
    """
    out_dir = Path(out_dir)
    docs = {d.doc_id: d for d in corpus.documents}
    by_page: dict[tuple[str, int], list[Observation]] = {}
    for fact in corpus.facts.values():
        for obs in fact.observations:
            by_page.setdefault((obs.doc_id, obs.page), []).append(obs)

    report = {"pages_checked": 0, "text_observations": 0,
              "figure_observations": 0, "failures": []}

    for doc in corpus.documents:
        pdf = out_dir / doc.path
        for page in range(1, doc.pages + 1):
            text = _page_text(pdf, page)
            numbers = {int(n.replace(",", "")) for n in _NUMBER.findall(text)}
            obs_here = by_page.get((doc.doc_id, page), [])
            text_values = {o.value for o in obs_here if o.channel in ("text", "table")}
            fig_values = {o.value for o in obs_here if o.channel == "figure"}
            report["pages_checked"] += 1
            report["text_observations"] += sum(1 for o in obs_here if o.channel in ("text", "table"))
            report["figure_observations"] += sum(1 for o in obs_here if o.channel == "figure")

            for value in text_values:
                if value not in numbers:
                    report["failures"].append(
                        f"{doc.doc_id} p{page}: text fact {value} not found in the text layer")
            for value in fig_values - text_values:
                if value in numbers:
                    report["failures"].append(
                        f"{doc.doc_id} p{page}: figure-only value {value} is readable as text")

            for obs in obs_here:
                x0, y0, x1, y1 = obs.bbox
                if not (0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H):
                    report["failures"].append(
                        f"{doc.doc_id} p{page}: bbox {obs.bbox} outside the page")

    if report["failures"]:
        raise AssertionError("text-layer verification failed:\n  " +
                             "\n  ".join(report["failures"][:10]))
    return report


def load_corpus(out_dir: Path) -> Corpus:
    """Rebuild the in-memory corpus from `ground_truth.json`.

    Reading the artifact back proves the ground truth is a real, reloadable
    record rather than a side effect of the build process.
    """
    out_dir = Path(out_dir)
    data = json.loads((out_dir / "ground_truth.json").read_text())
    corpus = Corpus()
    for d in data["documents"]:
        corpus.documents.append(DocRecord(
            doc_id=d["doc_id"], kind=d["kind"], path=d["path"],
            meta=d["meta"], acl=d["acl"], pages=d["pages"]))
    for f in data["facts"]:
        key = FactKey.from_dict(f["key"])
        corpus.facts[key] = Fact(
            key=key,
            observations=[Observation.from_dict(o) for o in f["observations"]],
        )
    return corpus
