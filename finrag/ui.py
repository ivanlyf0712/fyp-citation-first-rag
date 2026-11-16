"""Rendering helpers for the demo, kept out of the Streamlit script.

Pure functions only: cropping the exact region a citation points at, and
formatting an answer for a table cell.
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image

ANSWERED = {"answered"}

STATUS_LABEL = {
    "answered": "answered",
    "refused": "refused (cannot cite)",
    "not_found": "not found",
    "unparseable": "could not parse the question",
}


def format_answer(answer) -> str:
    if answer.status in ANSWERED:
        return f"HK${answer.value}m"
    return STATUS_LABEL.get(answer.status, answer.status)


def crop_region(build_dir: Path, doc_path: str, page: int,
                bbox: tuple[float, float, float, float],
                dpi: int = 150, pad: float = 8.0) -> Image.Image:
    """Crop the cited region of a PDF page.

    The stored bbox uses PDF coordinates with the origin at the bottom-left;
    PyMuPDF uses top-left, so the y values are mirrored against the page height.
    """
    path = Path(build_dir) / doc_path
    with pymupdf.open(path) as doc:
        pdf_page = doc[page - 1]
        height = pdf_page.rect.height
        x0, y0, x1, y1 = bbox
        clip = pymupdf.Rect(x0 - pad, height - y1 - pad, x1 + pad, height - y0 + pad)
        clip = clip & pdf_page.rect           # never read outside the page
        pix = pdf_page.get_pixmap(clip=clip, dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def page_image(build_dir: Path, doc_path: str, page: int, dpi: int = 110) -> Image.Image:
    path = Path(build_dir) / doc_path
    with pymupdf.open(path) as doc:
        pix = doc[page - 1].get_pixmap(dpi=dpi)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def point_in_bbox(x: float, y: float, bbox, tol: float = 3.0) -> bool:
    """Is a PDF-space point inside a box (bottom-left origin)?"""
    l, b, r, t = bbox
    return (l - tol) <= x <= (r + tol) and (b - tol) <= y <= (t + tol)


def nearest_unit(units, x: float, y: float, max_distance: float = 25.0):
    """The unit containing the point, or the closest centre within range."""
    for unit in units:
        if point_in_bbox(x, y, unit.bbox):
            return unit
    best, best_d = None, max_distance
    for unit in units:
        l, b, r, t = unit.bbox
        dx = max(l - x, 0.0, x - r)
        dy = max(b - y, 0.0, y - t)
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < best_d:
            best, best_d = unit, distance
    return best
