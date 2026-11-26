#!/usr/bin/env python3
"""Read chart crops with a local vision model; store structured values.

    python scripts/read_figures.py --limit 14

Output: annotations/figures/<pdf-stem>.json — one record per figure with
{kind, title, values, source_note}. `unreadable` is a valid answer and carries no
values: a figure that invents a number is worse than one that admits it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.figures import CHART_TYPES  # noqa: E402

PROMPT = (
    "Look at this image from an annual report. Reply with ONE JSON object only: "
    '{"kind": "bar|line|pie|donut|area|scatter|photo|logo|unreadable", '
    '"title": "text in the image, or empty", '
    '"values": [{"label": "...", "value": 0}]}. '
    "Only include values you can actually read. If it is a photograph, use kind "
    '"photo" and no values.'
)


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crops", default="annotations/figures/bochk_annual_2024")
    ap.add_argument("--out", default="annotations/figures/bochk_annual_2024.json")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--model", default="HuggingFaceTB/SmolVLM-500M-Instruct")
    args = ap.parse_args()

    from PIL import Image
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(args.model, dtype=torch.float32)

    results = []
    for path in sorted(Path(args.crops).glob("*.png"))[:args.limit]:
        image = Image.open(path).convert("RGB")
        messages = [{"role": "user", "content": [{"type": "image"},
                                                 {"type": "text", "text": PROMPT}]}]
        prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(text=prompt, images=[image], return_tensors="pt")
        out = model.generate(**inputs, max_new_tokens=160)
        text = processor.batch_decode(out, skip_special_tokens=True)[0]
        record = parse_json(text)
        kind = str(record.get("kind", "unreadable")).lower()
        if kind not in CHART_TYPES:
            kind = "unreadable"
        values = record.get("values") if kind not in ("photo", "logo", "unreadable") else []
        values = [v for v in (values or []) if isinstance(v, dict)]
        results.append({"crop": path.name, "kind": kind,
                        "title": str(record.get("title", ""))[:120],
                        "values": values[:20]})
        print(f"{path.name}: {kind} {record.get('title','')[:40]!r} "
              f"{len(values)} values", flush=True)

    Path(args.out).write_text(json.dumps(results, indent=1) + "\n")
    print(f"\n{len(results)} figures -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
