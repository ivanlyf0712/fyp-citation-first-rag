# Spec — visual evidence

Decided with the project owner. Covers figures: charts and images that are not
tables and not prose.

## Decisions

1. **Both purposes.** Store a crop as part of the evidence record (visual
   citation), and let a figure answer a question on its own when it can.
2. **Linking.** A figure points to the text that describes it, chosen in order:
   an explicit reference ("Figure 3", "as shown below") → the nearest text block
   on the page → the section heading. The rule that fired is recorded.
3. **Structured extraction.** A vision model returns
   `{title, chart_type, series:[{label, value, unit}], source_note}`; the crop is
   stored beside it. A figure it cannot read is marked `unreadable` and carries
   no values. A figure that invents a number is worse than one that admits it.
4. **No relational database.** Storage stays JSONL + `.npz` + an in-memory
   graph. Cross-filing statistics are `pandas` on JSONL, not a schema.
5. **Chart-like figures only.** Sample first: a heuristic shortlist of large,
   non-page-sized regions, then a vision pass to confirm. Bohai's 11 figures are
   portraits; BOC has 112 regions including genuine charts; Tencent 408.
6. **Evaluation.** Five chart questions, scored by exact value like everything
   else, reported as a separate set. No LLM judge.

## Why figures are different

A table row is text and can be checked by string comparison. A figure is pixels:
the number is not in the PDF's text layer at all. So a figure's values must be
extracted once, stored as data, and cited alongside the crop.

## Failure modes to guard

- **Reading a logo as a chart.** `chart_type` must be one of a closed set, and
  `unreadable` is allowed.
- **Hallucinated values.** Every extracted value is tied to the crop; a question
  answered from a figure must cite the figure unit.
- **Wrong linkage.** If the rule fired is "nearest block", the citation says so;
  the reader can see the link was positional, not explicit.

## Out of scope

- Scanned documents (no OCR path).
- Figure-to-figure relationships.
- Image search (retrieval stays over units; a figure is cited, not searched by
  pixels).


## Status, 26 November

Linking and crops are built: BOC's 112 figure regions, 14 chart-like candidates,
108 links by nearest block and 4 by explicit reference, crops stored under
`annotations/figures/bochk_annual_2024/`.

Extraction is blocked on model quality: `SmolVLM-500M` answers "Chart" and
returns no values. `scripts/read_figures.py --model <2B+ VLM>` is ready; a 3B
model or a hosted vision API is required before V5 and V6 can run.
