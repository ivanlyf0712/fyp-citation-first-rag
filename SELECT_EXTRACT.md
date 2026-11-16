# Select then extract — tried, and it is worse

## Result

| set | agent (chat) | select-then-extract |
|---|---|---|
| 19 fair paraphrases | 12.7 correct | **3 correct, 14 declined** |
| 14 concept-first | 12.0 correct | **5 correct, 6 declined** |

Three variants tried: candidates from the full search, candidates restricted to
table rows, and a pool widened to 200 hits. All three failed the same way — the
model declined, because the right label was usually not in the list it was given.

## Why it failed

- **Candidate pool.** Retrieval returns mostly prose units; after filtering to
  table rows, only 2–12 usable labels remained for a question. The right row was
  often absent, so the only honest answer was "none of these".
- **Labels lost their numbers.** With numbers hidden, two rows with the same label
  from different statements became indistinguishable — the exact ambiguity the
  numbers were helping resolve.
- **Long note labels.** Many candidates were whole sentences from notes, not line
  items, because table rows there are unstructured text.

## What this means

The decomposition the literature uses (FinQA-style cell referencing) assumes a
clean table schema: a small set of well-formed columns and rows. Our parser
produces rows, but not a reliable schema — the same limitation that broke the
column check and the cell units.

**The agent remains the best configuration**: 0.67 with `deepseek-chat`, **0.76
with `deepseek-reasoner`**. The model matters more than the pipeline shape, and
the ceiling is the parsed structure.
