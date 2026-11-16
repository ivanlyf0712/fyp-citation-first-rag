# Specification — citation-first retrieval

## The problem

A RAG system can return a number that no document supports. On financial
documents this is not a hallucination in the usual sense: every figure may be
real and correctly copied, and the *total* may still be wrong because one
contributing document was never retrieved.

Conventional RAG retrieves passages, generates an answer, and cites afterwards.
Citation is a post-hoc annotation, so an answer can outrun its evidence.

## The method

1. **Retrieve citeable units, not passages.** A unit is one span with a
   document, page, bounding box, quote and value. The retriever's output type is
   the citation type — there is no conversion step where a citation can be lost.
2. **Check coverage before answering.** For an aggregate, every contributing
   scope must be among the retrieved units. If one is missing, there is nothing
   to cite for it, and the system declines.
3. **Check support before returning.** Each cited quote must contain the value it
   is cited for, and the answer must equal the sum of the cited values.

An answer is returned only if both checks pass.

## Guarantees

- No number appears in an answer that is not the value of a cited unit, or the
  sum of cited values (checked by `check_support`).
- An aggregate is never answered from a subset (`check_coverage`).
- A question about a period the corpus does not cover is refused, because no
  unit can be cited for it.

## Non-goals at this milestone

- **No language model.** The reader is deterministic: it sums cited values.
  Generation quality is out of scope until an LLM is introduced.
- **No chart reading.** Figure values are oracle-assisted and flagged. The
  visual index retrieves pages; it does not read them.
- **No answer fluency.** The output is a number and its citations, not prose.

## Interfaces

```
build_units(corpus) -> list[Unit]
required_for_total(units, counterparty) -> {scope: [Unit]}
check_coverage(required, cited) -> Coverage
check_support(value, citations, derivation) -> (ok, checks, failures)
CitationFirst(corpus, out_dir, k_units).ask(question, mode) -> Answer
```

`Answer` carries `value`, `citations[]`, `coverage`, `verdict` and `status ∈
{answered, refused, not_found, unparseable}`.

## Invariants

1. Every unit has a quote and a bbox inside its page.
2. Coverage is 1.0 for every answered aggregate.
3. Every citation's quote contains its own value.
4. The answer equals the sum of the cited values for a derivation.
5. A wrong-period question is refused by both pipelines.
6. The app renders without exception.

## Measurement

[EVAL.md](../EVAL.md) for outcomes and the retrieval-depth curve;
[VISUAL.md](../VISUAL.md) for text-to-image retrieval;
[OCR_DEGRADATION.md](../OCR_DEGRADATION.md) for the extraction assumption;
[docs/METRICS.md](METRICS.md) for definitions and their sources.
