#!/usr/bin/env python3
"""Compare table extraction: PyMuPDF's find_tables vs Docling.

    python scripts/table_compare.py [--pdf PATH] [--pages N]

Both tools are asked to find tables on the same real pages. Agreement is
measured by bounding-box IoU, because neither tool is ground truth: a table
found by one and missed by the other is a disagreement, not an error, and the
report says so.

The output is TABLE_COMPARE.md plus a small sample of each tool's first table,
so the numbers can be eyeballed rather than trusted.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pymupdf

DEFAULT_PDF = ("/Users/ivanlee/Documents/FYP/9-Archive/ESG-Previous-Topic/"
               "Dataset/ESG Reports/0003_HK-China-Gas_ESG-Report_2025.pdf")


def iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix0 >= ix1 or iy0 >= iy1:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    return inter / union if union else 0.0


def pymupdf_tables(pdf: Path, n_pages: int):
    rows = []
    with pymupdf.open(pdf) as doc:
        for page in list(doc)[:n_pages]:
            height = page.rect.height
            found = page.find_tables()
            for t in found.tables:
                x0, y0, x1, y1 = t.bbox
                rows.append({
                    "page": page.number + 1,
                    "bbox": (x0, y0, x1, y1),
                    "norm": (x0, height - y1, x1, height - y0),  # to bottom-left
                    "rows": len(t.rows),
                    "cols": t.col_count,
                    "cells": len(t.cells),
                    "sample": [str(c) for c in (t.extract() or [[""]])[0][:3]],
                })
    return rows


def docling_tables(pdf: Path, n_pages: int):
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    started = time.perf_counter()
    try:
        result = converter.convert(pdf, page_range=(1, n_pages))
    except TypeError:
        result = converter.convert(pdf)
    elapsed = time.perf_counter() - started

    rows = []
    for table in result.document.tables:
        prov = table.prov[0] if table.prov else None
        box = None
        page_no = None
        if prov is not None:
            page_no = prov.page_no
            b = prov.bbox
            box = (b.l, b.t, b.r, b.b)          # docling: origin bottom-left
        try:
            frame = table.export_to_dataframe()
            shape = (len(frame), len(frame.columns))
            sample = [str(v) for v in frame.iloc[0].tolist()][:3]
        except Exception:
            shape, sample = (0, 0), []
        rows.append({"page": page_no, "bbox": box, "rows": shape[0],
                     "cols": shape[1], "cells": shape[0] * shape[1],
                     "sample": sample})
    return rows, elapsed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=DEFAULT_PDF)
    ap.add_argument("--pages", type=int, default=20)
    args = ap.parse_args()
    pdf = Path(args.pdf)

    t0 = time.perf_counter()
    pm = pymupdf_tables(pdf, args.pages)
    pm_time = time.perf_counter() - t0

    try:
        dc, dc_time = docling_tables(pdf, args.pages)
    except Exception as exc:  # pragma: no cover - depends on install
        print(f"Docling unavailable: {type(exc).__name__}: {exc}")
        dc, dc_time = [], 0.0

    # agreement: a PyMuPDF table is "matched" if some Docling box overlaps it
    matched = 0
    for row in pm:
        best = 0.0
        for other in dc:
            if other["bbox"] is None:
                continue
            same_page = (other["page"] == row["page"])
            if not same_page:
                continue
            best = max(best, iou(row["norm"], other["bbox"]),
                       iou(row["norm"], (other["bbox"][0], other["bbox"][3],
                                         other["bbox"][2], other["bbox"][1])))
        if best >= 0.5:
            matched += 1

    lines = [f"# Table extraction on a real filing", "",
             f"`{pdf.name}`, first {args.pages} pages.", "",
             "| tool | tables | cells | mean cells/table | time |",
             "|---|---|---|---|---|"]
    if pm:
        lines.append(f"| PyMuPDF `find_tables` | {len(pm)} | "
                     f"{sum(r['cells'] for r in pm)} | "
                     f"{sum(r['cells'] for r in pm) / len(pm):.0f} | {pm_time:.1f}s |")
    if dc:
        lines.append(f"| Docling | {len(dc)} | {sum(r['cells'] for r in dc)} | "
                     f"{sum(r['cells'] for r in dc) / max(len(dc), 1):.0f} | "
                     f"{dc_time:.1f}s |")

    lines += ["", f"Tables detected by both (IoU ≥ 0.5): **{matched}** of "
                  f"{len(pm)} found by PyMuPDF."]
    if dc and not matched:
        lines.append("")
        lines.append("No agreement at all — one of the two is likely using a "
                     "different page coordinate origin. Check the samples below "
                     "before drawing a conclusion.")

    if pm:
        lines += ["", "## PyMuPDF — first table", "",
                  f"page {pm[0]['page']}, {pm[0]['rows']}×{pm[0]['cols']} cells", "",
                  "`" + " | ".join(str(x) for x in pm[0]["sample"]) + "`"]
    if dc:
        lines += ["", "## Docling — first table", "",
                  f"page {dc[0]['page']}, {dc[0]['rows']}×{dc[0]['cols']}", "",
                  "`" + " | ".join(str(x) for x in dc[0]["sample"]) + "`"]

    Path("TABLE_COMPARE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
