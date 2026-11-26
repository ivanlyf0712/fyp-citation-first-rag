# Adding a filing

Three commands. Parsing is the slow part (≈5 s/page, cached); everything else is
seconds.

```bash
# 1. parse — one page at a time, cached per page
python scripts/build_unit_corpus.py --pdf samples/other_annual.pdf \
    --out annotations/corpus/other_units.jsonl

# 2. map the concept list onto rows and write questions
python scripts/new_filing.py --units annotations/corpus/other_units.jsonl \
    --out annotations/questions_other.jsonl

# 3. score the agent on them
python scripts/score_agent.py --units annotations/corpus/other_units.jsonl \
    --semantic --rerank --sections --workers 4 \
    --questions annotations/questions_other.jsonl --out results/other.md
```

## Step 2 is a draft, not ground truth

`new_filing.py` matches 13 fixed concepts to rows by label, preferring an exact
label over one that merely contains the phrase. It prints every mapping so it can
be checked:

```
ok   1,843,842,128.00  p 12  What were the total assets?
ok     913,328,962.00  p 19  What were the loans and advances to customers?
```

On the Bohai report all 13 mapped correctly. On a differently-worded filing some
will fail or pick a neighbouring row — that is what the printed table is for. Do
not quote numbers from an unreviewed mapping.

## What this gives you

- **Generalisation evidence**: the same 13 questions on a different bank.
- **A cross-language check**: run it on the Chinese filing and the labels simply
  map to Chinese rows, since the matcher works on the document's own labels.

## Status

| filing | parsed | questions | scored |
|---|---|---|---|
| Bohai 2024 (English) | 4,989 units | 60 across three sets | yes |
| Tencent 2025 (Chinese) | 10,052 units | 15 | yes, 7/15 |
| BOC Hong Kong 2024 (English) | 9,819 units, 313 pp | 10 | **6/10**, see [BOCHK.md](BOCHK.md) |
