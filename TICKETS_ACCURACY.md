# Tickets — accuracy and speed

| # | Ticket | Status |
|---|---|---|
| C1 | Column-aware context: header prepended to row units + prompt rule | `[x]` |
| C2 | Cell-level units with TOPLEFT→PDF conversion; wrong-column answer rejected | `[x]` built, rejected for answering (see ACCURACY.md) |
| C3 | `search_smart`: query expansion + RRF + `bge-reranker-base` | `[ ]` |
| C4 | `--workers` parallel scoring, identical outcomes | `[x]` |
| C5 | Re-measure 41 questions and write `ACCURACY.md` | `[x]` |
| C7 | Evidence-level check: cite the unit that answers, not merely one that agrees | `[~]` column check done; year-free questions open |
| C6 | Update README + AGENT_SPEC with the new tool and units | `[ ]` |

Definition of done: paraphrase correct ≥ 7/10, wrong not increased, 31-question
batch under 60 s, all tests passing.
