# Spec — retrieval refinement, four arms

## Goal

Raise paraphrase retrieval (value-R@5 **0.20**) without losing label-derived
retrieval (**0.90**), measured on the same 41 questions and 4,989 units.

Not a goal: reproducing corpchat's stack. Components are adopted only if they
earn their place; a component that fails is reported as a failure.

## Arms

| arm | change | hypothesis |
|---|---|---|
| A0 | baseline: BM25 + dense + RRF over `quote + channel` | reference |
| A1 | representation: embed/search `header :: label`, digits dropped | row vectors are mostly digits; removing them sharpens meaning |
| A2 | retrieval expansion: 3 LLM rewrites per question, BM25+dense per rewrite, RRF across all | question vocabulary is the failure, not the index |
| A3 | dedupe: collapse rows with the same label and value across pages | five slots are wasted on copies of one row |
| A4 | reranker: `bge-reranker-base` over the fused top-20 | a cross-encoder picks better than RRF alone |

## Protocol

- units: `annotations/corpus/units.jsonl` (4,989, rows + text).
- questions: label-derived (31) and paraphrase (10); same as prior runs.
- metric: value-R@5 (does the top 5 contain a unit carrying the gold value) and
  exact rank of the required unit.
- adoption bar: paraphrase value-R@5 +0.10 absolute, label-derived >= 0.87.
- everything reported, including failures.
- no bge-m3: English corpus, 1024 dims, no evidence it helps.

## After the matrix

Re-run the agent on the best arm: concept-first (14 questions, three repeats) and
paraphrase (10). Skip label-derived (saturated at 29–30/31).

## Landing

Each arm is a flag; the app and agent keep current defaults until a winner is
declared. Deliverable: `RETRIEVAL_REFINEMENT.md`.
