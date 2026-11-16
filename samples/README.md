# Sample filings

The PDFs used in the evaluation are not distributed here. Put an annual report
in this folder and point the scripts at it:

- `scripts/build_unit_corpus.py --pdf samples/<file>.pdf --out annotations/corpus/units.jsonl`
- `scripts/score_agent.py --units annotations/corpus/units.jsonl ...`

Any text-layer PDF works; scanned filings additionally need OCR.
