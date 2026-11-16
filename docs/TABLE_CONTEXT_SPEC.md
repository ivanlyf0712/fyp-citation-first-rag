# Spec — table-level context (after two failed verification ideas)

## What failed, and why

Two attempts to make the system choose the right row:

**Label agreement by similarity.** Compare the question with the cited row's
label, reject if they are too far apart. Measured on ten hand-checked pairs:

| pairs | bge-small cosine |
|---|---|
| correct label vs question | 0.63 – 0.84 |
| wrong label vs question | 0.54 – 0.62 |

The ranges overlap, so no threshold separates them. Short domain labels are all
close in embedding space.

**Label agreement by cross-encoder.** `bge-reranker-base` scores pairs, not
vectors — correct pairs returned 0.05, 0.06, 0.08, 0.09, 0.17, 0.97; wrong pairs
0.00. The logits are near zero for label-length text: the model is trained on
passages and does not calibrate on five-word strings.

**Label lookup tool** (`find_row`, lexical match over labels). No gain:
12 and 10 correct against a 12.7 baseline. The model was not failing to *find*
the label; it was failing to *choose* between rows it could already see.

## Conclusion

The errors are selection errors, and a single-row snippet gives the model no
context to select from. Verification after the fact cannot repair a blind choice.

## Proposed change

**Give the model the table, not the row.**

1. **Segment tables**: group row units on a page by vertical adjacency (gap
   <= 6 pt, same x-range). A block is the statement.
2. **Block tool**: `read_table(unit_id)` returns every row in the block, with the
   header row and section title.
3. **Answer from the block**: the model sees `Operating expenses | 10,488,740 |
   10,713,146` beside `Operating expenses | 26,325 | 26,033`, and the section
   tells it which is the Group's.
4. **Check**: the cited row must be inside the block that was read, and its label
   must share a word with the question (lexical, exact substring — now usable
   because the model chose from a visible finite set).

## Evaluation

19 fair paraphrase questions, three runs, same configuration. Adoption bar:
>= 0.75 correct (from 0.67), wrong not above 4.

## Risks

- Block segmentation merges side-by-side tables — the same defect that broke the
  column check.
- Token cost per question rises (~20-40 rows).
- If segmentation is wrong, the failure mode returns.
