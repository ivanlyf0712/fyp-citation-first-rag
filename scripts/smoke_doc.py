#!/usr/bin/env python3
"""Smoke test the whole sample document.

    python scripts/smoke_doc.py [--pdf PATH] [--from 1] [--to 277]

Parses every page with one loaded model, records per-page units, rows, timing
and any failure, and writes SMOKE_DOC.md. A page that raises is recorded and the
run continues: the point is to find the pages that break, not to stop at one.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.ingest import parse_pages  # noqa: E402

PDF = Path("samples/bohai_bank_annual_2024.pdf")
OUT = Path("SMOKE_DOC.md")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(PDF))
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--to", dest="end", type=int, default=277)
    args = ap.parse_args()

    started = time.time()
    done = {"n": 0}

    def progress(page: int, entry: dict) -> None:
        done["n"] += 1
        if done["n"] % 10 == 0 or entry["error"]:
            elapsed = time.time() - started
            rate = elapsed / done["n"]
            left = rate * (args.end - args.start + 1 - done["n"])
            print(f"p{page}: {entry['units']}u {entry['rows']}r {entry['seconds']}s"
                  f"{' ERROR ' + entry['error'] if entry['error'] else ''}"
                  f" | {elapsed/60:.1f} min elapsed, ~{left/60:.1f} min left",
                  flush=True)

    pages = list(range(args.start, args.end + 1))
    units, stats = parse_pages(Path(args.pdf), pages, progress=progress)

    ok = [s for s in stats if not s["error"]]
    failed = [s for s in stats if s["error"]]
    blank = [s for s in stats if s["blank"]]
    total_secs = sum(s["seconds"] for s in stats)
    with_rows = [s for s in ok if s["rows"]]
    lines = ["# Smoke test — whole document", "",
             f"`{Path(args.pdf).name}`, pages {args.start}–{args.end} "
             f"({len(stats)} pages).", "",
             "| measure | value |", "|---|---|",
             f"| pages parsed | {len(ok)} |",
             f"| pages failed | {len(failed)} |",
             f"| pages with no text layer | {len(blank)} |",
             f"| units | {len(units)} |",
             f"| table rows | {sum(1 for u in units if u.source == 'docling-row')} |",
             f"| units with a number | {sum(1 for u in units if u.numbers)} |",
             f"| pages with at least one row | {len(with_rows)} |",
             f"| total parse time | {total_secs/60:.1f} min |",
             f"| mean per page | {total_secs/len(stats):.1f} s |", ""]

    slowest = sorted(ok, key=lambda s: -s["seconds"])[:5]
    lines += ["## Slowest pages", "", "| page | units | rows | seconds |", "|---|---|---|---|"]
    for s in slowest:
        lines.append(f"| {s['page']} | {s['units']} | {s['rows']} | {s['seconds']} |")

    if failed:
        lines += ["", "## Failed pages", "", "| page | error |", "|---|---|"]
        for s in failed:
            lines.append(f"| {s['page']} | {s['error']} |")

    if blank:
        lines += ["", f"Pages with no text layer (require OCR): "
                      f"{', '.join(str(s['page']) for s in blank)}"]

    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
