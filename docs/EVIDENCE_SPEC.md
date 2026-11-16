# Spec — strengthening the evidence

The prototype works; the evidence for it is thin: one document, questions written
by someone who had already read the table, and a corpus that answers them by
keyword.

This spec covers the three things that change that, in order of how much they
change the conclusion.

## B1 — Concept-first question set

**What:** ~12 questions written from what a reader of an annual report would ask
("what was the net profit?", "what was the NPL ratio?"), chosen **before** looking
at which units can answer them, then mapped mechanically to a unit and a gold
value. Questions the corpus cannot answer are kept and labelled unanswerable.

**Why:** the existing 31 questions were generated from row labels, so they
contain the answer's own words. They measure retrieval, not answering. A
concept-first set is what a user actually asks, and it will contain questions the
corpus cannot answer — which is realistic.

**Honest limitation:** the author of these questions has read this document, so
this is *concept-first*, not blind. A genuinely blind set needs a second person;
that item stays open.

**Test:** report coverage (how many questions map to a unit), and accuracy on the
mapped subset. Compare with the label-derived set on the same corpus.

## B2 — Second filing

**What:** the same protocol on a different bank's annual report: parse, build
units, run the templated protocol (rows whose labels match the Bohai ones), and
compare paraphrase accuracy.

**Why:** one document cannot distinguish "the method works" from "the method
works on Bohai". This is the single most load-bearing piece of evidence.

**Blocker:** no second PDF on disk; needs one dropped into `samples/`.

**Test:** accuracy on the second filing within 10 points of the first, or a
documented reason why not.

## B3 — Multi-citation with cell units

**What:** prompt the model to cite **every** unit whose numbers it states, then
re-run the cell corpus.

**Why:** the cell experiment failed for one reason — a sentence stating a value
and its change cited only the value's cell, so support failed. If the model cites
both cells, the rejection disappears and cells give year-level enforcement.

**Test:** templated correct back to >= 28/31 with zero wrong, and wrong-column
answers rejected.

## Measurement protocol

Rows corpus (4,989 units) unless the ticket says otherwise; temperature 0; four
workers; outcomes counted as correct / wrong / rejected / declined; rejected and
declined are never merged with wrong.
