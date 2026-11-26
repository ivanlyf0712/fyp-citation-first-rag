#!/usr/bin/env python3
"""Read chart crops with a vision model and store structured values.

    python scripts/read_figures.py [--crops DIR] [--out FILE]

Uses the vision-capable chat model on the configured gateway (image input,
JSON-only reply, low reasoning effort). `unreadable` is a valid answer and
carries no values: a figure that invents a number is worse than one that admits
it. Local VLMs were tried first; SmolVLM-500M classified charts but could not
read values, and multi-GB downloads are blocked on this network.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.figures import CHART_TYPES  # noqa: E402

PROMPT = (
    'Return ONLY JSON: {"kind": "bar|line|pie|donut|area|scatter|photo|logo|unreadable", '
    '"title": "...", "values": [{"label": "<panel>: <category>", "value": <number>}]} '
    "listing every value you can read. No explanation."
)


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def _encode(path: Path, max_side: int = 900) -> str:
    """Downscale before sending: large crops slowed the model and it timed out."""
    from io import BytesIO

    from PIL import Image

    image = Image.open(path).convert("RGB")
    if max(image.size) > max_side:
        scale = max_side / max(image.size)
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def read_image(path: Path) -> dict:
    key = os.environ["LITELLM_API_KEY"]
    base = os.environ["LITELLM_BASE_URL"].rstrip("/")
    model = os.environ.get("VISION_MODEL", "deepseek-flash")
    b64 = _encode(path)
    response = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "reasoning_effort": "low", "max_tokens": 4000,
              "messages": [{"role": "user", "content": [
                  {"type": "text", "text": PROMPT},
                  {"type": "image_url",
                   "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]},
        timeout=180)
    response.raise_for_status()
    message = response.json()["choices"][0]["message"]
    record = parse_json(message.get("content") or "")
    if not record:                       # some models put JSON in the reasoning
        record = parse_json(message.get("reasoning_content") or "")
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crops", default="annotations/figures/bochk_annual_2024")
    ap.add_argument("--out", default="annotations/figures/bochk_annual_2024.json")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    results = []
    for path in sorted(Path(args.crops).glob("*.png"))[:args.limit]:
        try:
            record = read_image(path)
        except Exception as exc:                      # noqa: BLE001
            print(f"{path.name}: FAILED {exc}")
            record = {}
        kind = str(record.get("kind", "unreadable")).lower()
        if kind not in CHART_TYPES:
            kind = "unreadable"
        values = record.get("values") if kind not in ("photo", "logo", "unreadable") else []
        values = [v for v in (values or [])
                  if isinstance(v, dict) and isinstance(v.get("value"), (int, float))]
        results.append({"crop": path.name, "kind": kind,
                        "title": str(record.get("title", ""))[:150],
                        "values": values[:40]})
        print(f"{path.name}: {kind:>9} · {len(values):>2} values · "
              f"{str(record.get('title',''))[:50]}", flush=True)

    Path(args.out).write_text(json.dumps(results, indent=1) + "\n")
    print(f"\n{len(results)} figures -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
