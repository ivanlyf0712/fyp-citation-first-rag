# Retrieval refinement — four arms and two combinations

4,989 units; 31 label-derived and 10 paraphrase questions. Bar set before the
run: paraphrase value-R@5 **+0.10** over baseline, label-derived no worse than
**0.71**. Every arm is reported.

| arm | label-derived | paraphrase | verdict |
|---|---|---|---|
| A0 baseline (BM25 + dense + RRF) | 0.74 | 0.20 | reference |
| A1 representation (`header :: label`, digits dropped) | **0.87** | 0.20 | helps labels only — fails paraphrase bar |
| A2 retrieval-level expansion (3 rewrites, RRF) | 0.81 | **0.30** | meets bar |
| A3 dedupe near-identical rows | 0.81 | 0.20 | fails paraphrase bar |
| A4 reranker over fused top-20 | **0.94** | **0.40** | meets bar |
| **A2 + A4** expansion then rerank | 0.87 | **0.80** | **winner** |
| A1 + A4 label then rerank | 0.94 | 0.30 | strong on labels, weak on paraphrase |

## Decision

**Adopt A2 + A4**: expansion, then RRF, then cross-encoder rerank. Paraphrase
retrieval rises 4× (0.20 → 0.80) while label-derived stays well above the floor.

A4 alone was the best single change; expansion by itself only reached 0.30. The
combination is what works, and the ordering matters: reranking the *expanded*
candidate pool beats reranking the plain one (0.40 → 0.80 on paraphrases).

A1 is the most interesting negative: dropping the digits from the embedded text
raises label-derived from 0.74 to 0.87, so the hypothesis was right about row
vectors being number-dominated — but it does nothing for paraphrases, because
labels are still words the question does not use.

## Agent re-run on the winning arm

| set | before | after |
|---|---|---|
| paraphrase correct | 7/10 | **8/10** |
| paraphrase wrong | 1 | 2 |
| concept-first correct (3 runs) | 9.7/14 (9–11) | **11.0/14 (10–12)** |
| concept-first wrong (3 runs) | 0–1 | **0** |

The retrieval gain reached the answers: +1.3 questions on average on the
concept-first set, and no wrong answers in any of the three runs.

## Cost

- reranker: `bge-reranker-base`, ~1.1 GB, loaded once, ~1 s per question.
- expansion: one extra LLM call per question, ~1 s.
- Total: about 2 s added per question, in exchange for +0.60 paraphrase recall.

## Not adopted

- **bge-m3 embeddings** — not tested; no evidence the multilingual encoder helps
  an English table corpus, and the disk cost is 2 GB.
- **Cell units** — tested earlier and rejected (see `ACCURACY.md`).
