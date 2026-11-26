#!/usr/bin/env python3
"""Baseline: retrieve whole pages by image similarity, then answer.

The multimodal-sounding alternative to citeable units: embed every rendered page
with CLIP, pick the top-k pages for the question, and let the model read their
text. Same model, same questions, same scoring as the citation-first runs.

    python scripts/baseline_page_image.py
"""
from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pymupdf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import answer_numbers, value_matches  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402

PDF = Path("samples/bohai_bank_annual_2024.pdf")
SETS = {"concept": "annotations/questions_blind.jsonl",
        "paraphrase": "annotations/questions_paraphrase2.jsonl"}
TOP_K = 3
PROMPT = """Answer the question from these pages of an annual report.
Reply with one short sentence containing the figure.

{pages}

Question: {question}"""


def main() -> int:
    from transformers import CLIPModel, CLIPProcessor

    model_id = "openai/clip-vit-base-patch32"
    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)

    print("rendering pages…", flush=True)
    images, texts, numbers = [], [], []
    with pymupdf.open(PDF) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=72)
            images.append(pix)
            texts.append(" ".join((page.get_text() or "").split())[:3000])

    from PIL import Image

    pil = [Image.frombytes("RGB", (p.width, p.height), p.samples) for p in images]
    print(f"embedding {len(pil)} pages with CLIP…", flush=True)
    page_vecs = []
    with torch.no_grad():
        for start in range(0, len(pil), 16):
            batch = pil[start:start + 16]
            inputs = processor(images=batch, return_tensors="pt")
            page_vecs.append(model.get_image_features(**inputs).pooler_output)
    page_vecs = torch.cat(page_vecs)
    page_vecs = page_vecs / page_vecs.norm(dim=-1, keepdim=True)

    lines = ["# Baseline — page-image retrieval (CLIP)", "",
             f"{len(pil)} pages embedded with `clip-vit-base-patch32`; top-{TOP_K} "
             "pages retrieved per question, answered from their text.", ""]
    for name, path in SETS.items():
        questions = [q for q in load_jsonl(Path(path)) if q.get("gold_value")]
        with torch.no_grad():
            q_inputs = processor(text=[q["question"] for q in questions],
                                 return_tensors="pt", padding=True)
            q_vecs = model.get_text_features(**q_inputs).pooler_output
            q_vecs = q_vecs / q_vecs.norm(dim=-1, keepdim=True)
        sims = (q_vecs @ page_vecs.T).numpy()

        def ask(i):
            q = questions[i]
            top = np.argsort(-sims[i])[:TOP_K]
            pages = "\n\n".join(f"[page {int(p)+1}] {texts[int(p)]}" for p in top)
            text, _usage = DeepSeekClient().complete(
                [{"role": "user", "content": PROMPT.format(pages=pages,
                                                           question=q["question"])}])
            nums = answer_numbers(text)
            if not nums:
                outcome = "declined"
            elif any(value_matches(n, q["gold_value"]) for n in nums):
                outcome = "correct"
            else:
                outcome = "wrong"
            return {"question": q["question"], "outcome": outcome,
                    "pages": [int(p) + 1 for p in top], "answer": text[:100]}

        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(ask, range(len(questions))))

        counts = Counter(r["outcome"] for r in rows)
        lines += [f"## {name} ({len(rows)} questions)", "",
                  "| correct | wrong | declined |", "|---|---|---|",
                  f"| {counts.get('correct',0)} | {counts.get('wrong',0)} | "
                  f"{counts.get('declined',0)} |", ""]
        for r in rows:
            lines.append(f"| {r['question'][:55]} | pages {r['pages']} | {r['outcome']} |")
        lines.append("")

    Path("BASELINE_PAGE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
