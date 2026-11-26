# The graph layer

Units are nodes. Edges are what the parser already knows: **same label**,
**same table block**, **same section**. Nothing is learned and the graph rebuilds
from units in milliseconds.

## Why it exists

The project's finding is that verification can prove a number is in a quote but
not that the quote answers the question. Scope is the missing link — a row called
`Operating expenses` exists on the primary statement and again in the notes, and
the text cannot tell them apart. The graph can: it holds both, and knows which is
under `V. ANALYSIS OF FINANCIAL STATEMENTS`.

```
Operating expenses | (10,488,740)   p18    statement   ← Group
Operating expenses | 11 | (10,488,740)  p136  note
Operating expenses | 26,325 | 26,033    p222  note       ← segment
Operating expenses | 48,479 | 68,655    p223  note
```

`related_rows(unit_id)` returns those twins, primary statement first. The agent
can call it when a row's scope is unclear.

## Multi-hop questions

A ratio cannot be answered by selecting one row. Labels are matched to rows, the
values are read, and the arithmetic is done in code — the model is not asked to
divide.

| question | rows | value | gold |
|---|---|---|---|
| implied tax rate | p18 + p18 | 0.0145 | 0.0145 ✓ |
| operating expenses / operating income | p18 + p18 | 0.4116 | 0.4116 ✓ |
| net interest share of income | p18 + p18 | 0.6099 | 0.6099 ✓ |
| impairment / operating income | p18 + p18 | 0.3791 | 0.3791 ✓ |
| net margin on operating income | p12 + p18 | 0.2063 | 0.2063 ✓ |

**5/5**, with two citations per answer and no language-model arithmetic.
[scripts/multihop_eval.py](scripts/multihop_eval.py), [MULTIHOP.md](MULTIHOP.md).

## What failed

Promoting a note row's primary twin into the retrieval pool before answering —
the obvious use — made paraphrase accuracy **worse**: 11 and 9 correct against a
12.7 baseline, with wrong answers rising to 7–8. Adding rows the model did not ask
for recreates the table-context failure: more candidates, more wrong selections.

So the graph stays a **linking and lookup layer**: it powers `related_rows` and
the multi-hop path, and it does not silently rewrite the retrieval order.
