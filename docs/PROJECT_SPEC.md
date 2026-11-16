# Project specification — citation-first retrieval over financial documents

*Last revised: 13 November 2026. Supersedes `docs/SPEC.md`, which describes the
earlier permission-aware pipeline now archived in `9-Archive/Permission-Aware-RAG/`.*

## The claim, in one sentence

**A system that verifies its answers against the text it cites removes invented
numbers completely, but does not remove answers that are faithful and wrong — a
real figure from the wrong row or the wrong year — and that residue is
measurable.**

This is deliberately narrow. The supervisor's position (email, November 2026) is
that a novel *combination* is a contribution provided the project identifies and
overcomes the challenges that only appear when the parts are combined. The claim
above is one of those challenges, and it is falsifiable: if enforcement also
removed misgrounding, or if the residue were negligible, the claim fails.

## Problem

An analyst asks a question of a 277-page annual report. Existing pipelines
retrieve text chunks and generate an answer. Some attach citations after the
fact. None checks whether the evidence actually supports the claim being made,
so a confident, cited, wrong answer is indistinguishable from a correct one.

## Gap

Published work covers the parts: typed evidence graphs over filings (HC-RAG),
multimodal graphs over documents (MMGraphRAG, MegaRAG), agentic retrieval over
page images (ViDoRAG), and permission-aware retrieval. What is missing is a
pipeline that decides whether the evidence available for a claim is *sufficient*
for it — before the answer is shown.

## Research questions

- **RQ1** Does citation-level verification eliminate unsupported numbers on real
  filings? *(Measured: yes — 4/4 invented numbers withheld.)*
- **RQ2** What does it miss? *(Measured: 4/4 answers using a real number from the
  wrong row survived.)*
- **RQ3** Can deterministic structure — column headers, unit granularity — close
  the gap without a second model? *(Partially: the column check fires only when
  the question names a year.)*
- **RQ4** What does retrieval contribute versus reading? *(Dense retrieval finds
  the right figure in the top 5 for 87–90% of label-derived questions; failures
  are reading and vocabulary, not search.)*

## System

```
PDF ──► Docling (layout, tables)  ─┐
   └──► PyMuPDF (text layer, boxes)┴──► units ──► retrieval ──► agent ──► verification ──► answer
                                        │           │            │            │
                                  text/row/cell  BM25 +     tools:      support,
                                  /figure        dense/RRF  search_*,  column,
                                                            read_unit   decline
```

- **Units** are the retrieval and citation unit: `(page, bbox, quote, value)`.
  Text units are paragraphs; table rows are row-level; cells exist for the
  column check; figures are captions only.
- **Retrieval**: BM25, dense (`bge-small-en-v1.5`), and RRF fusion. Expansion
  (`search_expanded`) rewrites the question into report vocabulary.
- **Agent**: a hand-written loop, JSON protocol, three tools plus expansion.
  DeepSeek via API; every call logged.
- **Verification**, applied to the prose: every number must appear in a cited
  quote; cited rows must hold the number in the asked-for year's column; refusals
  are classified separately from wrong answers.

## Evaluation

| set | questions | how written | role |
|---|---|---|---|
| label-derived | 31 | generated from row labels | retrieval ceiling |
| paraphrase | 10 | manual, label avoided | realistic wording |
| concept-first | 14 | written from reader questions before mapping | closest to real use |

Corpus: `samples/bohai_bank_annual_2024.pdf`, 277 pages, 4,989 units (rows +
text), plus a 7,369-unit variant with table cells. Every page parses; 0 failures.

**Protocol**: temperature 0, four workers, three repeats for any set under 30
questions. Outcomes are counted separately as correct / wrong / rejected /
declined — merging them hides the behaviour the project is about.

## Results so far

| measurement | value |
|---|---|
| retrieval value-R@5, label-derived | 0.74 RRF → **0.94** with rerank |
| agent correct, label-derived | 29–30 / 31 |
| retrieval value-R@5, paraphrase | 0.20 → **0.80** (expansion + rerank) |
| agent correct, paraphrase | 7 / 10 → **8 / 10** |
| agent correct, concept-first | 9.7 / 14 → **12.0 / 14** (11, 12, 13; three runs, zero wrong) |
| invented numbers shown with enforcement off | 4 / 10 → **0** with it on |
| real-but-wrong numbers shown with enforcement on | **4 / 10** |
| batch time, 31 questions | 27 s |

## What is not done

- **One document.** Every number above is Bohai Bank. A second filing is the
  single most load-bearing missing piece.
- **The question sets are mine.** Concept-first is not blind.
- **Charts.** Figure units carry captions only; no vision model reads a chart.
  The "multimodal" part of the title is currently tables, not images.
- **Permissions.** Deferred: a single-document, single-user prototype. The
  completeness predicate from the archived project has not been re-instantiated
  on real documents.
- **Cell units** were built and rejected for answering: a sentence states a value
  and its change, and one cell cannot cover both.

## Deliverables and dates

| date | deliverable |
|---|---|
| 24 Jan 2027 | interim report (20%) — spec, system, results above, limitations |
| 11–16 Jan 2027 | first presentation (10%) — live demo on a real filing |
| 18 Apr 2027 | final report |
| 19–24 Apr 2027 | final presentation; poster 21 Apr |

## Risks

| risk | mitigation |
|---|---|
| second filing collapses accuracy | report it as the finding; measure the drop rather than hide it |
| examiner rejects 14-question evidence | report ranges, three repeats, and say the set is small |
| "multimodal" challenged because charts are unread | scope the claim to tables; add a VLM only if time allows |
| permission layer absent | state it as deferred, not implied |

## Repository map

```
6-Code/
  app.py                 annotation bench (parse, click boxes, accept evidence, ask)
  finrag/                ingest, overlay, retrieval, vectors, agent, verification, metrics
  scripts/               build corpus, retrieval arms, agent scoring, enforcement, smoke test
  annotations/           accepted units, questions, runs, caches, vector indexes
  docs/                  this spec, agent spec, accuracy spec, evidence spec, metrics
  *.md                   results: EVAL, VECTORS, ACCURACY, EVIDENCE, ENFORCEMENT, SMOKE_DOC
9-Archive/               ESG project, permission-aware project (frozen, with READMEs)
```
