# Citation-first retrieval over financial documents

Ask a question about a 277-page annual report and get an answer in prose that
cites the page, the box and the exact quote it came from. If a number in the
answer cannot be found in a quote it cites, **the answer is withheld**.

The interesting part is what that guarantee does *not* catch — see
[The finding](#the-finding).

## Try it in five minutes

```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -r requirements.txt

# 1. put an annual report (text-layer PDF) in samples/
#    e.g. samples/my_report.pdf

# 2. parse it into units — one page ~5 s, cached per page
python scripts/build_unit_corpus.py --pdf samples/my_report.pdf \
    --out annotations/corpus/units.jsonl

# 3. run the annotation + question bench
streamlit run app.py
```

In the browser: upload the PDF, parse a page range, click any box on the page to
see its crop and quote, accept it as evidence, then open the **Ask** tab.

> Asking requires a DeepSeek API key (sidebar field, session only). Everything
> else runs offline.

## The finding

Verification compares the answer against the quotes it cites. Measured on a real
HKEX filing, with the answer's evidence removed from the corpus so the question
is unanswerable:

| | enforcement off | enforcement on |
|---|---|---|
| invented a number that appears in no quote | 4 | **0 shown** |
| used a real number from the wrong row, year or entity | 4 | **4 still shown** |
| declined | 2 | 1 |

**Citation support cannot see scope.** The check proves a number exists in a
quote; it cannot prove the quote answers the question. A figure from the 2023
column, a segment instead of the Group, or the notes instead of the primary
statement all pass.

Full detail: [ENFORCEMENT.md](ENFORCEMENT.md), [RESTRICTION.md](RESTRICTION.md).

## Accuracy

19 fair paraphrased questions, three runs, frozen configuration
([RESULTS.md](RESULTS.md)):

| question style | correct |
|---|---|
| uses the report's own line-item wording (31) | 0.94 |
| concept questions, written before mapping (14) | 0.86 |
| fair paraphrases (19) | **0.67** (0.76 with `deepseek-reasoner`) |

The gap is selection, not retrieval: dense retrieval puts the right figure in the
top 5 for 80–90% of questions, and the model then reads the wrong row.

## How it works

```
PDF ─► Docling (layout, tables)  ─┐
  └──► PyMuPDF (text layer, boxes)┴─► units ─► retrieval ─► agent ─► verification
                                       │          │           │          │
                                 page, bbox,   BM25 +     tools:     numbers in
                                 quote, value  embeddings  search,    quotes,
                                               + rerank    read      column, scope
```

- **Units** are the citation: `(page, bbox, quote, value)`. Text = paragraphs,
  tables = rows, plus optional cell units.
- **Retrieval**: BM25 + `bge-small-en-v1.5`, fused with RRF, reranked with
  `bge-reranker-base`, query expansion for report vocabulary.
- **Agent**: a hand-written JSON tool loop (no framework) over DeepSeek.
- **Verification**: every number must appear in a cited quote; year columns are
  checked when the question names one; refusals are counted separately from
  wrong answers.

Specs: [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md),
[docs/AGENT_SPEC.md](docs/AGENT_SPEC.md),
[docs/RETRIEVAL_SPEC.md](docs/RETRIEVAL_SPEC.md).

## Reproduce the numbers

```bash
export DEEPSEEK_API_KEY=...
bash scripts/reproduce.sh
```

Runs the unit corpus build, three repeats of each question set, the restriction
experiment, and the test suite. Results land in `results/frozen/`.

## Layout

```
app.py            annotation bench and Ask tab
finrag/           ingest, retrieval, vectors, agent, verification, metrics
scripts/          corpus build, evaluations, restriction experiment, smoke test
tests/            60 tests, no network required
docs/             specs: project, agent, retrieval, accuracy, evidence
*.md              results and audits — start with RESULTS.md
annotations/      question sets and accepted units (data is gitignored)
```

## Limitations

- **One document** in the frozen results; a second (Chinese) filing parses but
  retrieves at 0.20 because `bge-small` is English-only.
- **60 questions total**, written by the author. [AUDIT.md](AUDIT.md) lists three
  that are ambiguous.
- **Charts are not read** — figures carry captions only.
- **Permissions are simulated** by removing evidence, not enforced.
- **Negative results are documented**: table-level context (0.54),
  select-then-extract (0.16–0.36) and label-similarity checks all failed —
  see [TABLE_CONTEXT.md](TABLE_CONTEXT.md), [SELECT_EXTRACT.md](SELECT_EXTRACT.md).

## Tests

```bash
python -m pytest -q      # 60 passed
```
