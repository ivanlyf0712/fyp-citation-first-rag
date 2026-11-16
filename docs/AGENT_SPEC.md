# Agent specification — LLM steers and writes, citations are enforced

## What it does

Answers a question about a real financial document in **natural language**, using
tools to find evidence, and returns the unit ids it relied on. An answer whose
numbers are not present in its citations is **rejected before it is shown**.

Four decisions, taken with the project owner:

1. the LLM both chooses tools and writes the prose;
2. model is DeepSeek via API (key supplied later; a stub drives tests);
3. the loop is hand-written, ~150 lines, no framework;
4. scoring is deterministic — a number extracted from the prose, compared with
   gold, plus the citation checks. No LLM judge.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `search_bm25` | `query`, `k` | up to `k` units: id, page, quote, numbers |
| `search_semantic` | `query`, `k` | same, from the embedding index |
| `read_unit` | `unit_id` | the full quote, page, doc and numbers |

Tools never return a number that is not in a stored quote. There is no
free-text retrieval: everything the model sees is a citeable unit.

## Protocol

JSON only, one object per assistant turn.

```json
{"tool": "search_bm25", "query": "net profit", "k": 5}
{"answer": "The Group's net profit was RMB5,255,815 thousand in 2024.",
 "citations": ["U:4bf507ea4a"]}
```

Tool results come back as a user message: `{"tool_result": [...]}`. The loop stops
at the first object containing `answer`, or after **6 tool calls**, after which
the model is asked once to answer with what it has.

## Enforcement

An answer is accepted only if all hold:

1. `citations` is non-empty and every id exists;
2. every number in the answer appears in at least one cited quote;
3. the answer contains at least one number (a claim, not a hedge);
4. at most 12 tool calls were made (runaway guard).

Otherwise the answer is replaced by a refusal naming the failed check. The
rejection is logged; it is the measurement of how often the model outruns its
evidence.

## Logging

One JSONL record per question in `annotations/runs/`:

```
question, model, steps[{tool, args, n_results}], answer, citations,
verification{accepted, checks, failures}, tokens_in, tokens_out, latency_ms
```

No key, no prompt text secrets — the prompt is hashed.

## Scoring

For each annotated question:

- **correct** — a number in the answer equals the gold value;
- **wrong** — a number is given and differs;
- **rejected** — the enforcement refused it (counted separately: a valid answer
  that was refused is a cost, not a success);
- **no answer** — the model declined or produced no number.

Reported per question and in aggregate, next to the retrieval-only numbers, so
the contribution of the LLM is visible rather than assumed.

## Non-goals

- Multi-agent orchestration, memory, or planning beyond the tool loop.
- Fine-tuning.
- Any claim about answer quality beyond "the number is right and it is cited".

## Failure modes to expect

- The model answers from parametric knowledge without calling a tool → rejected
  by check 2.
- The model cites a unit it never read → accepted only if the number really is in
  that quote, which is the point of checking the quote rather than the id.
- The model splits a figure across a citation boundary → the number is not found
  in the quote → rejected; the fix is better retrieval, not a looser check.
