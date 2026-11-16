# Results — one frozen configuration

Every number below comes from this one setup. Nothing else in the repository is a
result; earlier files are in `results/history/`.

## Configuration

| component | setting |
|---|---|
| corpus | `samples/bohai_bank_annual_2024.pdf`, 277 pages, **4,989 units** (rows + paragraphs) |
| retrieval | BM25 + `bge-small-en-v1.5`, fused with RRF, then `bge-reranker-base` over the top 30 |
| query expansion | one LLM rewrite call, plus deterministic finance synonyms (gross loans/deposits, impairment losses) |
| scope | every unit carries its page-heading section; Group-level questions weight primary statements 1.8× and notes 0.7× |
| model | `deepseek-chat`, temperature 0 |
| verification | every number must be in a cited quote; rows must hold it in the asked-for year's column; refusals counted separately |

## Accuracy — three runs each

| question set | correct | wrong | rejected | declined |
|---|---|---|---|---|
| concept-first (14) | 13, 12, 13 — **mean 12.7** | 0, 1, 0 | 0 | 1, 1, 1 |
| paraphrase (10) | 6, 7, 5 — **mean 6.0** | 2, 2, 2 | 0–1 | 1–3 |

Rates: concept-first **0.90**, paraphrase **0.60** overall.

**Corrected for question quality:** three of the ten paraphrase questions are
ambiguous (see [AUDIT.md](AUDIT.md)). On the seven well-posed ones the three runs
score 6/7, 7/7, 4/7 — **mean 0.81**. Report both numbers; the gap is the
instrument, not the system.

The paraphrase set is weaker and noisier than earlier single runs suggested
(7–8/10). Three runs are the honest number; one run is not.

### Model comparison (19 fair paraphrases, 2 runs each)

| model | correct | wrong |
|---|---|---|
| `deepseek-chat` | 12.7 (12, 14, 12, 12, 10) | 4–6 |
| `deepseek-reasoner` | **14.5** (15, 14) | **2** |

The reasoning model halves the wrong answers and gains ~2 questions. It is also
slower — a 19-question run takes ~3 minutes against ~40 seconds. Selection, not
reading, is where the smaller model was losing.

### Larger fair-paraphrase set (19 questions)

Added on 13 Nov to replace the 10-question set's tiny sample:

| run | correct | wrong | declined |
|---|---|---|---|
| 1 | 14 | 4 | 1 |
| 2 | 12 | 6 | 1 |
| 3 | 12 | 4 | 3 |

**Mean 12.7/19 = 0.67.** Lower than the 0.86 on the seven well-posed questions of
the old set, and a better estimate because the sample is larger. The failures are
the same class as before: lookalike rows ("gross" wording, neighbouring line
items), not invented numbers.

## When the evidence is out of reach

Every unit carrying the answer removed — the permission case reduced to its
load-bearing part:

| outcome | count (of 14) |
|---|---|
| correct | 0 |
| **wrong** | **2** |
| rejected | 2 |
| declined | 10 |

The system refuses 12 of 14 times. Twice it answers from a lookalike row — a real
number, correctly cited, wrong for the question. **That is the completeness gap**:
nothing in the pipeline notices that the evidence it can see is insufficient.

## Cost

- ~4 s per question at four-way parallelism (~16 s single-threaded).
- One LLM expansion call per question; reranker loaded once (~1.1 GB).
- A 31-question run takes about 30 s; a 10-question run about 40 s including model load.

## Reproduce

```bash
cd 6-Code
python scripts/build_unit_corpus.py                 # once; cached per page
python scripts/score_agent.py --units annotations/corpus/units.jsonl \
    --semantic --rerank --sections --workers 4 \
    --questions annotations/questions_blind.jsonl --out results/frozen/concept.md
python scripts/restriction_eval.py                  # RESTRICTION.md
```

## What these numbers do not cover

- **One document.** Bohai Bank only.
- **Sets written by the author.** Concept-first is not blind.
- **Charts are not read.** Figure units carry captions; no vision model.
- **Permissions are simulated** by removing evidence, not enforced by an access
  model.
