#!/usr/bin/env python3
"""The baseline most people would ship: chunk the text, retrieve, answer.

Same document, same questions, same model, same retrieval budget (top-5) and
the same reranker as the citation-first pipeline. The only differences are the
unit of retrieval (text chunks, not citeable units) and the absence of any
check on the answer.

    python scripts/baseline_chunk_rag.py
"""
from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.agent_rag import answer_numbers, value_matches  # noqa: E402
from finrag.llm import DeepSeekClient  # noqa: E402
from finrag.real_eval import load_jsonl  # noqa: E402
from finrag.retrieve import Bm25Index, Chunk  # noqa: E402
from finrag.vectors import _model  # noqa: E402

PDF = Path("samples/bohai_bank_annual_2024.pdf")
SETS = {
    "concept": Path("annotations/questions_blind.jsonl"),
    "paraphrase": Path("annotations/questions_paraphrase2.jsonl"),
}
PROMPT = """Answer the question using only these passages from a financial report.
Reply with one short sentence containing the figure.

{passages}

Question: {question}"""


def chunks_from_pdf(pdf_path: Path, size: int = 700, overlap: int = 120) -> list[dict]:
    out = []
    with pymupdf.open(pdf_path) as doc:
        for page_no, page in enumerate(doc, start=1):
            text = " ".join((page.get_text() or "").split())
            if not text:
                continue
            step = size - overlap
            for start in range(0, len(text), step):
                piece = text[start:start + size]
                if len(piece) > 120:
                    out.append({"id": f"p{page_no}-{start}", "page": page_no,
                                "text": piece})
    return out


def main() -> int:
    chunks = chunks_from_pdf(PDF)
    print(f"{len(chunks)} text chunks from {PDF.name}")

    bm25 = Bm25Index()
    for c in chunks:
        bm25.add(Chunk(doc_id=c["id"], page=c["page"], text=c["text"]))
    bm25.finalize()

    print("encoding…", flush=True)
    model = _model("BAAI/bge-small-en-v1.5")
    matrix = model.encode([c["text"] for c in chunks], batch_size=64,
                          normalize_embeddings=True, convert_to_numpy=True,
                          show_progress_bar=False).astype(np.float32)
    from sentence_transformers import CrossEncoder
    reranker = CrossEncoder("BAAI/bge-reranker-base")
    from finrag.agent_rag import rrf_fuse
    by_id = {c["id"]: c for c in chunks}

    def ask(job):
        question, gold = job
        bm = bm25.ranked_docs(question, k=40)
        qv = model.encode([question], normalize_embeddings=True,
                          convert_to_numpy=True)[0].astype(np.float32)
        dense = [chunks[i]["id"] for i in np.argsort(-(matrix @ qv))[:40]]
        fused = rrf_fuse([bm, dense])[:20]
        pairs = [(question, by_id[uid]["text"]) for uid in fused]
        scores = reranker.predict(pairs)
        top = [fused[i] for i in np.argsort(-np.asarray(scores))[:5]]
        passages = "\n\n".join(f"[p{by_id[uid]['page']}] {by_id[uid]['text']}"
                               for uid in top)
        text, _usage = DeepSeekClient().complete(
            [{"role": "user", "content": PROMPT.format(passages=passages,
                                                       question=question)}])
        numbers = answer_numbers(text)
        retrieved = " ".join(by_id[uid]["text"].replace(",", "") for uid in top)
        invented = [n for n in numbers
                    if f"{n:g}" not in retrieved and f"{n:.0f}" not in retrieved]
        if not numbers:
            outcome = "declined"
        elif any(value_matches(n, gold) for n in numbers):
            outcome = "correct"
        else:
            outcome = "wrong"
        return {"question": question, "gold": gold, "answer": text[:120],
                "outcome": outcome, "invented": bool(invented)}

    lines = ["# Baseline — chunk RAG, no verification", "",
             f"{len(chunks)} text chunks (700 chars, 120 overlap), top-5 after rerank, "
             "same model and questions as the citation-first runs.", ""]
    for name, path in SETS.items():
        questions = [(q["question"], q["gold_value"])
                     for q in load_jsonl(path) if q.get("gold_value")]
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(ask, questions))
        counts = Counter(r["outcome"] for r in rows)
        invented = sum(1 for r in rows if r["invented"])
        lines += [f"## {name} ({len(rows)} questions)", "",
                  "| correct | wrong | declined | answers with a number absent from the passages |",
                  "|---|---|---|---|",
                  f"| {counts.get('correct',0)} | {counts.get('wrong',0)} | "
                  f"{counts.get('declined',0)} | **{invented}** |", ""]
        for r in rows:
            lines.append(f"| {r['question'][:55]} | {r['gold']:,.0f} | {r['outcome']} | "
                         f"{'invented' if r['invented'] else ''} |")
        lines.append("")
    # The decisive comparison: the answer is removed from the corpus. The
    # citation-first system refuses 12 of 14 here; what does a chunk RAG do?
    questions = [(q["question"], q["gold_value"])
                 for q in load_jsonl(SETS["concept"]) if q.get("gold_value")]

    def ask_restricted(job):
        question, gold = job
        needle = f"{gold:,.0f}".replace(",", "")
        keep = [i for i, c in enumerate(chunks)
                if needle not in c["text"].replace(",", "")
                and f"{abs(gold):g}" not in c["text"].replace(",", "")]
        qv = model.encode([question], normalize_embeddings=True,
                          convert_to_numpy=True)[0].astype(np.float32)
        scores = matrix[keep] @ qv
        order = [keep[i] for i in np.argsort(-scores)[:20]]
        pairs = [(question, chunks[i]["text"]) for i in order]
        rerank = reranker.predict(pairs)
        top = [order[i] for i in np.argsort(-np.asarray(rerank))[:5]]
        passages = "\n\n".join(f"[p{chunks[i]['page']}] {chunks[i]['text']}" for i in top)
        text, _usage = DeepSeekClient().complete(
            [{"role": "user", "content": PROMPT.format(passages=passages,
                                                       question=question)}])
        numbers = answer_numbers(text)
        if not numbers:
            outcome = "declined"
        elif any(value_matches(n, gold) for n in numbers):
            outcome = "correct"
        else:
            outcome = "wrong"
        return {"question": question, "gold": gold, "answer": text[:120],
                "outcome": outcome}

    with ThreadPoolExecutor(max_workers=4) as pool:
        restricted = list(pool.map(ask_restricted, questions))
    rcounts = Counter(r["outcome"] for r in restricted)
    lines += ["", "## Evidence removed (14 concept questions)", "",
              "Every chunk containing the answer deleted first. The citation-first "
              "system refuses 12 of 14 here.", "",
              "| correct | wrong | declined |", "|---|---|---|",
              f"| {rcounts.get('correct',0)} | {rcounts.get('wrong',0)} | "
              f"{rcounts.get('declined',0)} |", ""]
    for r in restricted:
        lines.append(f"| {r['question'][:55]} | {r['gold']:,.0f} | {r['outcome']} |")

    Path("BASELINE_CHUNK.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
