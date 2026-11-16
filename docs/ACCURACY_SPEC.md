# Spec — accuracy and speed, from the measured failures

## Where the errors actually are

At full scale the agent scores **30/31** on templated questions and **5/10** on
paraphrases. Every failure is one of three kinds:

1. **wrong column** — the row is right, the year is not (`10,713,146` for 2023
   when 2024 was asked);
2. **wrong row** — a neighbouring line item (`interest income from loans` for
   `net interest income`);
3. **wrong page** — the model cites a unit whose quote does not hold its number,
   which the enforcement catches.

Retrieval is not the bottleneck for (1) and (3): dense retrieves the correct
figure in the top 5 for 87–90% of templated questions. The errors are in *which
part of the retrieved row* gets read, and in *which row* is chosen for a
paraphrase.

## Changes, in order

### C1 — Column-aware context (cheap, immediate)

*What:* prepend the table's header row to every row unit shown to the model
(`"2024 | 2023 | Change | Increase (%)" :: "Net profit | 5,255,815 | …"`), and add
one rule to the system prompt: the first numeric column is the current year.

*Why:* the header is already in the corpus; the model simply never sees it. This
targets failure (1) directly.

*Test:* the three column-error questions must flip; no templated question may
regress.

### C2 — Cell-level units (structural)

*What:* emit one unit per table **cell**, quote `"{row label}: {cell text}"`, bbox
from Docling's cell box converted from TOPLEFT to the PDF convention.

*Why:* a row quote contains both years, so citing the row "supports" either
figure. Until the unit is a cell, the enforcement **cannot** detect a wrong
column — the guarantee is weaker than it looks.

*Test:* a deliberately wrong-column answer must now be **rejected** by
`verify_answer`.

### C3 — Query expansion + fusion + rerank (`search_smart`)

*What:* one tool that takes the question, asks the model for up to three
paraphrases, runs BM25 and dense for each, fuses with RRF, reranks the top 20
with `bge-reranker-base`, and returns the top 10.

*Why:* paraphrases score 0.20 value-R@5; the model's own rewording is exactly
what retrieval lacks. This is corpchat's stack, at the scale this project needs.

*Test:* paraphrase value-R@5 and agent accuracy both rise; report the cost per
question.

### C4 — Parallel scoring (speed)

*What:* `--workers N` over questions in `score_agent.py`, default 4.

*Why:* questions are independent; the run is I/O-bound on the API. 3–4× on the
batch with no behavioural change.

*Test:* identical outcomes, wall time under a minute for 31 questions.

## What is deliberately not done

- Fine-tuning, model swaps, agent frameworks: none address the observed errors.
- More tool calls: most runs finish in two; the cap only bounds the worst case.

## Measurement protocol

Same 41 questions, same units (4,989), same model, temperature 0. Report per
question set: correct / wrong / rejected / declined, cited-required rate, mean
latency. A change ships only if paraphrases improve **without** an increase in
wrong answers.
