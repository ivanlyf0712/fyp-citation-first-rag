#!/usr/bin/env python3
"""Parse every page once and keep the units.

    python scripts/build_unit_corpus.py [--from 1] [--to 277]

Writes annotations/corpus/units.jsonl. Each page is cached separately, so an
interrupted run resumes and a later change only re-parses the pages that changed
— the smoke test threw its units away, which is a mistake this script exists to
prevent.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymupdf  # noqa: E402

from finrag.ingest import (  # noqa: E402
    _units_from_page,
    load_cache,
    page_has_text,
    save_cache,
)

PDF = Path("samples/bohai_bank_annual_2024.pdf")
CACHE = Path("annotations/cache")
OUT = Path("annotations/corpus/units.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--to", dest="end", type=int, default=277)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--pdf", default=str(PDF))
    args = ap.parse_args()

    from docling.document_converter import DocumentConverter

    pdf_path = Path(args.pdf)
    converter = DocumentConverter()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    parsed = cached = 0

    with pymupdf.open(pdf_path) as pdf, out_path.open("w") as out:
        for i, page_no in enumerate(range(args.start, args.end + 1), start=1):
            units = load_cache(CACHE, pdf_path, page_no, page_no)
            if units is None:
                pdf_page = pdf[page_no - 1]
                if page_has_text(pdf_page):
                    try:
                        result = converter.convert(str(pdf_path), page_range=(page_no, page_no))
                        units = _units_from_page(result.document, pdf_page, pdf_path.name)
                    except Exception as exc:                     # noqa: BLE001
                        print(f"p{page_no}: FAILED {exc}", flush=True)
                        units = []
                    save_cache(CACHE, pdf_path, units, page_no, page_no)
                else:
                    units = []
                parsed += 1
            else:
                cached += 1
            for unit in units:
                out.write(json.dumps(unit.as_dict(), sort_keys=True) + "\n")
            if i % 10 == 0:
                elapsed = time.time() - started
                print(f"p{page_no} · parsed {parsed} cached {cached} · "
                      f"{elapsed/60:.1f} min", flush=True)

    print(f"done: {parsed} parsed, {cached} from cache, -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
