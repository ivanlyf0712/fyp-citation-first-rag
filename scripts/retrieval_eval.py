#!/usr/bin/env python3
"""Retrieval quality of the conventional arm.

    python scripts/retrieval_eval.py

BM25 over page text, scored against the probes' gold evidence with Recall@10,
nDCG@10 and MRR. This is the number that makes "the graph is not a retriever" a
measured statement rather than an assertion: the graph resolves facts by key and
would score 1.0 by construction, so it is reported separately and not compared.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.documents import load_corpus  # noqa: E402
from finrag.probes import build_probes  # noqa: E402
from finrag.retrieve import Bm25Index, evaluate  # noqa: E402


def main() -> int:
    build = Path("build")
    corpus = load_corpus(build)
    probes = build_probes(corpus)

    index = Bm25Index.from_corpus(corpus, build)
    result = evaluate(index, probes, k=10)

    lines = ["# Retrieval — the conventional arm", "",
             "BM25 over page text, one chunk per page. Scored against the gold "
             "evidence of each probe (the documents that together support the "
             "answer). k = 10, the BEIR convention.", "",
             "| probe type | n | Recall@10 | nDCG@10 | MRR |",
             "|---|---|---|---|---|"]
    for qtype, m in result["by_type"].items():
        lines.append(f"| {qtype} | {m['n']} | {m['recall']:.3f} | "
                     f"{m['ndcg']:.3f} | {m['mrr']:.3f} |")
    o = result["overall"]
    lines.append(f"| **all** | {result['n']} | {o['recall']:.3f} | "
                 f"{o['ndcg']:.3f} | {o['mrr']:.3f} |")
    lines += ["", "## Reading", "",
              "A `total` probe needs all the counterparty's cell memos plus the "
              "group statement, so its recall is capped by how many of those fit "
              "in the top ten — this is what a chunk retriever can and cannot do "
              "for an aggregation question.", "",
              "The graph arm is not reported here. It resolves facts by canonical "
              "key, so its retrieval is exact by construction; scoring it against "
              "a ranked metric would compare a lookup to a search. The comparison "
              "that matters arrives with the page-image index."]

    Path("RETRIEVAL.md").write_text("\n".join(lines) + "\n")
    (build / "retrieval.json").write_text(json.dumps(result, indent=2) + "\n")
    print("\n".join(lines[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
