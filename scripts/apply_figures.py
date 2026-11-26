#!/usr/bin/env python3
"""Attach extracted figure values to their units, so a chart becomes evidence.

    python scripts/apply_figures.py --units annotations/corpus/bochk_units.jsonl \
        --figures annotations/figures/bochk_annual_2024.json \
        --out annotations/corpus/bochk_figures.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.real_eval import load_jsonl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", required=True)
    ap.add_argument("--figures", required=True)
    ap.add_argument("--links", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    figures = json.loads(Path(args.figures).read_text())
    by_key = {}
    for record in figures:
        stem = record["crop"].rsplit(".", 1)[0]          # p86_03c89c9525
        page, _, fragment = stem.partition("_")
        by_key[(int(page.lstrip("p")), fragment)] = record

    units = load_jsonl(Path(args.units))
    enriched, used = [], 0
    for unit in units:
        if unit.get("channel") == "figure":
            key = (unit["page"], unit["unit_id"].split(":")[-1][:10])
            record = by_key.get(key)
            if record and record.get("values"):
                # group by panel so the model reads a small table, not a wall
                panels: dict[str, list[str]] = {}
                for v in record["values"]:
                    label = str(v["label"])
                    panel, _, item = label.partition(": ")
                    if not item:
                        panel, item = "values", label
                    panels.setdefault(panel.strip(), []).append(
                        f"{item} {v['value']}")
                body = " | ".join(f"{name}: " + "; ".join(items)
                                  for name, items in panels.items())
                unit = dict(unit)
                unit["quote"] = (f"[chart] {record.get('title') or 'figure'} — {body}")
                unit["numbers"] = [float(v["value"]) for v in record["values"]]
                unit["chart_kind"] = record["kind"]
                used += 1
        enriched.append(unit)

    out = Path(args.out)
    out.write_text("\n".join(json.dumps(u, sort_keys=True) for u in enriched) + "\n")
    print(f"{used} figure units enriched; {len(enriched)} units -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
