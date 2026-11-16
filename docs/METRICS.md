# Metrics

Every number in the reports is computed from run records by `finrag/evaluate.py`
and `finrag/metrics.py`. Definitions and sources:

| Metric | Definition | Source |
|---|---|---|
| **Correct** | the answer equals the gold value; for an unanswerable probe, a refusal counts as correct | task definition |
| **Wrong** | an answer was given and differs from gold, or an unanswerable probe was answered | task definition |
| **Declined** | an answerable probe was refused | this project |
| **Coverage** | cited scopes ÷ required scopes | this project |
| **Full coverage** | share of answers whose coverage reached 1.0 | this project |
| **Recall@k / nDCG@k / MRR** | page retrieval quality against gold evidence, k = 10 | Järvelin & Kekäläinen (2002); BEIR, Thakur et al. (2021) |
| **Wilson interval** | score interval for a proportion | Wilson (1927); Brown, Cai & DasGupta (2001) |
| **Citation precision / recall** | cited evidence vs needed evidence | ALCE, Gao et al. (2023) |

## Why coverage is the headline

The claim is not that citation-first retrieval finds more documents. It is that
an answer can only be *complete* if every contributing scope is cited, and the
coverage number is that statement made measurable. Precision alone would not
catch it: a partial sum with four perfectly correct citations has precision 1.0.

## Threats to validity

- **Small corpus, easy queries.** Retrieval recall is near-saturated for BM25
  because every query names its counterparty and there are 62 documents. The
  numbers are a control, not an estimate of retrieval difficulty.
- **Oracle figures.** Chart values come from the generator. The visual index
  retrieves pages, but no model read a chart; every figure unit is flagged.
- **No language model.** Nothing here measures generation, fluency or
  hallucination of prose. The reader is deterministic.
- **Synthetic estate.** Exact ground truth is bought with realism; the document
  shapes are modelled, not sampled from real filings.
