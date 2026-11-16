# Accuracy and speed — first pass

C1 (table header + column rule) and C4 (parallel scoring), measured on the same
41 questions and 4,989 units.

| question set | metric | before | after |
|---|---|---|---|
| paraphrase (10) | correct | 5 | **6** |
| | wrong | 3 | **1** |
| | rejected | 2 | 1 |
| | declined | 0 | 2 |
| templated (31) | correct | 30 | 29 |
| | wrong | 1 | **0** |
| | declined | 0 | 2 |
| batch time | 31 questions | 92 s | **27 s** |

## Reading

The column rule moved answers from *wrong* to *declined*: the model now notices
it cannot tell which year a figure belongs to and says so. That is the correct
behaviour — and it means the next gain must come from evidence the model can
actually read, not from instructions.

Speed improved 3.4× with four workers; outcomes are unchanged by concurrency.

Targets: paraphrase correct >= 7/10 (at 6), wrong not increased (met: 3 -> 1),
batch < 60 s (met: 27 s). Remaining work is C2 (cells) and C3 (expansion).

## Second pass — deterministic column check

When the question names a year, every cited row must hold the number in that
year's column (header row read from the page). No model judgement involved.

| measurement | before | after |
|---|---|---|
| paraphrase correct | 6/10 | **7/10** |
| paraphrase wrong | 1 | 1 |
| paraphrase rejected | 1 | 1 |
| paraphrase declined | 2 | 1 |
| templated correct | 29/31 | 29/31 |

Target of 7/10 paraphrases is met, but the column check is what caught the
column errors in *templated* questions; the four grounded-wrong answers in the
evidence-removed experiment survive because those questions never name a year
("how much did the bank actually make that year?"). Withholding the year defeats
the check — so the remaining ticket is an evidence-level check, not a better
column rule.

## Third pass — cell-level units (C2)

7,369 units (rows + one unit per table cell, `"2024 · Net profit: 5,255,815"`).

| measurement | rows (4,989) | rows + cells (7,369) |
|---|---|---|
| retrieval value-R@5, templated, dense | 0.87 | **0.90** |
| retrieval value-R@5, templated, BM25 | 0.58 | **0.68** |
| agent correct, templated | 29/31 | 25/31 |
| agent rejected, templated | 0 | **6** |
| agent correct, paraphrase | 7/10 | 7/10 |
| agent wrong, paraphrase | 1 | 3 |

**Cells help retrieval and hurt answering.** The reason is structural: a sentence
usually states a value *and* its change ("5,255,815, up 3.44%"), which one cell
cannot cover, so the support check rejects an answer that is right. The row
covered both numbers; the cell does not.

Decision: rows remain the answering corpus. Cells are kept for the column check
and as the input to any future cell-citation work, which would need the model to
cite several units per sentence.
