"""Conventional retrieval over page text, as the RAG baseline.

The graph in `graph.py` is not a retriever: it resolves facts by canonical key,
so it cannot be compared to search. This module supplies the comparison that a
reviewer will ask for — BM25 over page text, ranked, scored with the standard
retrieval metrics (Recall@k, nDCG@k, MRR).

BM25 is chosen deliberately over an embedding model: it is deterministic, has no
dependency, and is a *strong* baseline on financial documents, where the query
and the evidence share exact terms (counterparty names, "exposure", desk names).
An embedding baseline would be the next rung; the point of this one is to make
the retrieval number real rather than assumed.

References: Robertson & Zaragoza (2009), *The Probabilistic Relevance Framework:
BM25 and Beyond*; nDCG after Järvelin & Kekäläinen (2002); the k=10 convention
after BEIR (Thakur et al., 2021).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from . import metrics

_TOKEN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")
STOP = {"the", "a", "an", "of", "for", "in", "on", "what", "is", "was", "to",
        "and", "at", "by", "with", "per"}


_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Latin words and numbers, plus Chinese character bigrams.

    Chinese has no spaces and single characters are too common to discriminate
    ("的", "年"), so adjacent-character pairs are the indexing unit — the usual
    choice for Chinese IR without a segmenter.
    """
    lowered = text.lower()
    out = [t for t in _TOKEN.findall(lowered)
           if t not in STOP and len(t) > 1]
    for run in _CJK_RUN.findall(lowered):
        out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return out


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    page: int
    text: str

    @property
    def cid(self) -> str:
        return f"{self.doc_id}:{self.page}"


class Bm25Index:
    """A page-level BM25 index over the rendered corpus."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.chunks: list[Chunk] = []
        self.tf: list[Counter[str]] = []
        self.df: Counter[str] = Counter()
        self.avgdl = 0.0
        self.n_docs = 0

    # -- construction ------------------------------------------------------
    @classmethod
    def from_corpus(cls, corpus, out_dir: Path) -> "Bm25Index":
        index = cls()
        out_dir = Path(out_dir)
        for doc in corpus.documents:
            with pymupdf.open(out_dir / doc.path) as pdf:
                for page_no, page in enumerate(pdf, start=1):
                    index.add(Chunk(doc.doc_id, page_no, page.get_text("text")))
        index.finalize()
        return index

    def add(self, chunk: Chunk) -> None:
        tokens = tokenize(chunk.text)
        counts = Counter(tokens)
        self.chunks.append(chunk)
        self.tf.append(counts)
        for term in counts:
            self.df[term] += 1
        self.n_docs += 1
        self.avgdl += len(tokens)

    def finalize(self) -> None:
        self.avgdl = self.avgdl / max(self.n_docs, 1)

    # -- scoring -----------------------------------------------------------
    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 10, allowed: set[str] | None = None
               ) -> list[tuple[str, int, float]]:
        """Return (doc_id, page, score), best first, one row per page."""
        terms = tokenize(query)
        scored: list[tuple[float, int]] = []
        for i, counts in enumerate(self.tf):
            if allowed is not None and self.chunks[i].doc_id not in allowed:
                continue
            length = sum(counts.values())
            score = 0.0
            for term in terms:
                f = counts.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * length / max(self.avgdl, 1e-9))
                score += self._idf(term) * f * (self.k1 + 1) / denom
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda t: (-t[0], self.chunks[t[1]].cid))
        return [(self.chunks[i].doc_id, self.chunks[i].page, s) for s, i in scored[:k]]

    def ranked_docs(self, query: str, k: int = 10,
                    allowed: set[str] | None = None) -> list[str]:
        """Document ranking, de-duplicated (the unit the probes are scored on)."""
        out: list[str] = []
        for doc_id, _page, _score in self.search(query, k=k, allowed=allowed):
            if doc_id not in out:
                out.append(doc_id)
        return out


def evaluate(index: Bm25Index, probes, k: int = 10) -> dict:
    """Recall@k, nDCG@k and MRR against the probes' gold evidence."""
    rows = []
    for probe in probes:
        if not probe.evidence:
            continue
        ranked = index.ranked_docs(probe.text, k=max(k, 20))
        rows.append({
            "qid": probe.qid,
            "type": probe.type,
            "recall": metrics.recall_at_k(ranked, probe.evidence, k),
            "ndcg": metrics.ndcg_at_k(ranked, probe.evidence, k),
            "mrr": metrics.reciprocal_rank(ranked, probe.evidence),
        })
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    return {
        "k": k,
        "n": len(rows),
        "overall": {
            "recall": round(metrics.mean([r["recall"] for r in rows]), 4),
            "ndcg": round(metrics.mean([r["ndcg"] for r in rows]), 4),
            "mrr": round(metrics.mean([r["mrr"] for r in rows]), 4),
        },
        "by_type": {
            t: {
                "n": len(rs),
                "recall": round(metrics.mean([r["recall"] for r in rs]), 4),
                "ndcg": round(metrics.mean([r["ndcg"] for r in rs]), 4),
                "mrr": round(metrics.mean([r["mrr"] for r in rs]), 4),
            }
            for t, rs in sorted(by_type.items())
        },
        "rows": rows,
    }
