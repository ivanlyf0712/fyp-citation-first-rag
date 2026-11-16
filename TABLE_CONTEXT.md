# Table-level context — tried, and it made things worse

## Result

Whole-statement context via `read_table` (9 rows of the income statement, header
and section attached), 19 fair paraphrase questions, three runs:

| run | correct | wrong | declined |
|---|---|---|---|
| 1 | 9 | 8 | 2 |
| 2 | 11 | 7 | 1 |
| 3 | 11 | 6 | 2 |

**Mean 10.3/19 (0.54)**, against 12.7 (0.67) with row-level retrieval. Wrong
answers rose from 4–6 to 6–8; declines fell. The model answered more often and
more wrongly.

## Why it failed

The hypothesis was that the model could not *see* enough to choose. It could; it
chooses badly. Given ten rows that all look like candidates —

```
Operating income        | 25,481,589
Operating expenses      | (10,488,740)
Profit before taxation  | 5,333,030
```

— a paraphrase like "what did the bank keep as profit" is answered from the wrong
line more often than with one row in view, because more numbers are in reach.

So the failure is **selection**, not visibility. More context increases the number
of plausible wrong answers.

## What the literature assumes that we lack

Chain-of-Table and TAT-QA-style systems either fine-tune the model on the task or
execute structured operations over the table. A zero-shot agent choosing a row
from a paraphrase has neither advantage.

## How to overcome it

**Decompose selection from extraction.** One model call, one decision:

1. retrieve top-10 candidate **labels** (no numbers);
2. ask the model to pick the label that answers the question — a short
   multiple-choice decision, auditable and countable;
3. the code takes the value from that row, deterministically;
4. verification compares the chosen label against the question's terms, which is
   now checkable because the model chose from an explicit list.

This turns an invisible reading error into a visible selection error, and makes
the number impossible to confuse with a neighbouring row's.

Alternative if that fails: fine-tune a small reranker on the ~60 question→label
pairs already annotated, or use a stronger model for selection only.
