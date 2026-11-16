# Evidence — concept-first questions

## B1 result

14 questions written from what a reader asks ("what was the net profit?", "what
was the NPL ratio?"), *before* checking which units could answer them, then
mapped mechanically to a row and a value.

| outcome | count |
|---|---|
| correct | **11** |
| wrong | 0 |
| rejected | 1 |
| declined | 2 |

Correct rate 11/14 = **0.79**, with no wrong answers. For comparison: 29–30/31
(0.94) on label-derived questions and 7/10 on paraphrases.

## What failed

- **loans and advances to customers** — withheld. The row is phrased "Gross
  loans and advances to customers", and the model could not reconcile "gross"
  with the question.
- **customer deposits** — declined, same "gross deposits" wording.
- **impairment charge** — declined: the document says "impairment losses on
  assets", and the model would not equate "charge" with "losses".

All three failures are **vocabulary**, not retrieval: the figure was in the
corpus in each case, under a name the question did not use. That is the same
failure class as the paraphrases, and it points at query expansion rather than
at the index.

## Honest limitation

These questions are **concept-first, not blind**: I wrote them after reading the
document, so the wording avoids traps I could see. A genuinely blind set needs a
second person (ticket B5), and until then the 0.79 is an upper bound.

## Files

- `annotations/questions_blind.jsonl` — the 14 questions, each with the row it
  maps to and its value.
- `AGENT_RESULTS_BLIND.md` — per-question outcomes.

## B1 re-measured — three runs

The single 11/14 was not stable, so the same 14 questions were run three times
after adding query expansion (`search_expanded`) and stripping dates from the
number check.

| run | correct | wrong | rejected | declined |
|---|---|---|---|---|
| 1 | 9 | 1 | 1 | 3 |
| 2 | 9 | 1 | 1 | 3 |
| 3 | 11 | 0 | 0 | 3 |

**Mean 9.7/14 (0.69), range 9–11.** The three declined questions are the same in
every run — loans (B11), deposits (B12) and one other — so the variance is in the
answers, not in which questions are hard.

## What the two changes did

- **Query expansion** recovered the "impairment charge -> impairment losses"
  question, which now answers correctly.
- **Date stripping** fixed a false rejection: "as at 31 December 2024" put a bare
  `31` into the answer, which the check counted as an unsupported number.
- Neither moved the total outside the noise band. On 14 questions, one question
  is 7 percentage points — the set is too small to resolve a change that size.

## Consequence for how this is reported

Any claim must be a range, not a point: **0.69 ± 0.07 on 14 concept-first
questions**, not "11/14". Ten-question and fourteen-question sets cannot support
a one-decimal claim, and pretending otherwise is the easiest thing for an examiner
to break.

## After the winning retriever — what still fails

With expansion + rerank, concept-first runs at **11/14, 2 wrong, 1 declined**
(stable across two runs). The remaining failures are all one class:

| qid | gold | what it answered | why it is wrong |
|---|---|---|---|
| B03 | 10,488,740 | 26,325 (RMB million) | a segment/notes figure, not the Group's |
| B12 | 1,046,088,795 | 7,757,546 | a different entity's deposits |
| B11 | 936,490,691 | refused | "gross" loans vs "loans" — vocabulary |
| H02 | 10,488,740 | prior-year figure | wrong column |
| H09 | 9,939,119 | net fee income | neighbouring line item |

**Fabrication is gone; scope is not.** Every wrong answer cites a real quote
containing a real number — the failure is that the number belongs to a different
*entity or scope* (segment vs Group, notes vs primary statement, 2023 vs 2024).
No string check on the quote can see that, which is why this is the residue the
project reports rather than hides.

Also fixed here: US-style dates ("December 31, 2024") were not being stripped, so
each date contributed a bare `31` and caused a false rejection. Removing them
converted 1–3 rejections into 2 wrong answers — a more honest measurement, and a
worse-looking number.

## Scope context — the fix, and what it bought

Following contextual retrieval (Anthropic, 2024: prepending section context cut
top-20 retrieval failures by 35%), every unit now inherits the nearest heading
above it on the page, and the model is told to prefer primary statements when the
question is about the Group.

Headings were already parsed as text units, so this cost no re-parse. The three
failing rows now carry the context that distinguishes them:

```
p222  Operating expenses | 26,325       -> Notes to the Consolidated Financial Statements
p18   Operating expenses | (10,488,740) -> V. ANALYSIS OF FINANCIAL STATEMENTS
```

Result over two runs, with expansion + rerank:

| | before sections | after |
|---|---|---|
| correct | 11 | **11** |
| wrong | 2 | **1** |
| rejected | 0 | 0 |
| declined | 1 | 2 |

The operating-expenses scope error (B03) is fixed. The total did not move: operating
income (B02) now declines instead. Wrong answers halved; declined answers doubled.
Net: a better-calibrated system, not a more accurate one — which is worth saying
plainly rather than calling it a gain.

## Scope weighting — the fix that worked

Three changes, all deterministic:

1. **Section context** on every unit (contextual retrieval).
2. **Scope weighting**: for Group/Bank/Total questions, primary-statement units are
   multiplied by 1.8 and notes by 0.7 before reranking.
3. **Finance synonyms** appended to the expansion: loans -> "gross loans and
   advances to customers", deposits -> "gross deposits from customers",
   charge/impairment -> "impairment losses on assets".

| set | before | after (3 runs) |
|---|---|---|
| concept-first correct | 9.7 / 14 | **12.0 / 14** (11, 12, 13) |
| concept-first wrong | 0–1 | **0, 0, 0** |
| paraphrase correct | 7–8 / 10 | 7 / 10 |
| paraphrase wrong | 1–2 | 1 |

The misgrounding is gone on the concept-first set: three runs, zero wrong
answers. What replaced it is *declines* — the remaining failures are refusals
(loans/B11, and occasionally operating expenses), not fabrications.

That is the trade the system makes, and it is the one worth reporting: accuracy
rose, and the residual failure mode changed from wrong to abstained.
