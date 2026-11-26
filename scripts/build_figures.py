#!/usr/bin/env python3
"""Link figures to their descriptions, store crops, and shortlist charts.

    python scripts/build_figures.py [--units annotations/corpus/bochk_units.jsonl]

No vision model is involved yet: this produces the links, the crops and the
shortlist that the extraction step consumes.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.figures import chart_candidates, link_figures, store_crop  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.sections import attach_sections  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", default="annotations/corpus/bochk_units.jsonl")
    ap.add_argument("--pdf", default="samples/bochk_annual_2024.pdf")
    ap.add_argument("--out", default="FIGURES.md")
    args = ap.parse_args()

    raw = attach_sections(load_jsonl(Path(args.units)))
    units = [SimpleNamespace(**u) for u in raw]
    figures = [u for u in units if u.channel == "figure"]
    candidates = chart_candidates(units)
    links = link_figures(units)
    by_id = {u.unit_id: u for u in units}

    crops_dir = Path("annotations/figures") / Path(args.pdf).stem
    stored = 0
    for fig in candidates[:40]:
        store_crop(Path(args.pdf), fig, crops_dir)
        stored += 1

    rules = Counter(link.rule for link in links)
    lines = ["# Figures", "",
             f"`{Path(args.pdf).name}`: {len(units)} units, **{len(figures)} figure "
             f"regions**, {len(candidates)} chart-like candidates "
             f"(>= 180x100 pt), {stored} crops stored.", "",
             "| link rule | figures |", "|---|---|"]
    for rule, count in rules.most_common():
        lines.append(f"| {rule} | {count} |")

    lines += ["", "| page | size (pt) | linked text | rule |", "|---|---|---|---|"]
    for link in links[:25]:
        fig = by_id[link.figure_id]
        w = fig.bbox[2] - fig.bbox[0]
        h = fig.bbox[3] - fig.bbox[1]
        text = by_id[link.text_id].quote[:60] if link.text_id else "—"
        lines.append(f"| {fig.page} | {w:.0f}x{h:.0f} | {text} | {link.rule} |")

    Path(args.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:14]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
