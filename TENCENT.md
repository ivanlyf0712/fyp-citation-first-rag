# Second document — Tencent 2025 (Chinese)

1975 table rows, 15 Chinese questions, `BAAI/bge-m3` (1024 dims).

| arm | Recall@5 | MRR |
|---|---|---|
| bm25 | **0.60** | 0.24 |
| dense | **0.47** | 0.30 |
| rrf | **0.73** | 0.46 |

| question | gold | BM25 | dense | RRF |
|---|---|---|---|---|
| 二零二五年的收入是多少？ | 751,766 | 28 | 9 | 13 |
| 二零二五年的毛利是多少？ | 422,593 | 4 | 2 | 2 |
| 二零二五年的經營盈利是多少？ | 241,562 | 2 | 3 | 1 |
| 二零二五年的除稅前盈利是多少？ | 277,249 | 2 | 1 | 2 |
| 二零二四年的收入是多少？ | 660,257 | 31 | 9 | 11 |
| 二零二四年的毛利是多少？ | 349,246 | 3 | 2 | 2 |
| 二零二三年的收入是多少？ | 609,015 | 8 | 8 | 1 |
| 二零二三年的毛利是多少？ | 293,109 | 3 | 17 | 4 |
| 二零二二年的經營盈利是多少？ | 110,827 | 8 | 3 | 2 |
| 二零二一年的收入是多少？ | 560,118 | 3 | 5 | 1 |
| 公司二零二五年的營業額是多少？ | 751,766 | 238 | 70 | 97 |
| 二零二五年公司賺了多少毛利？ | 422,593 | 4 | 10 | 2 |
| 二零二五年經營溢利是多少？ | 241,562 | 4 | 9 | 2 |
| 二零二五年除稅前利潤是多少？ | 277,249 | 2 | 1 | 2 |
| 二零二四年公司的營業額是多少？ | 660,257 | 161 | 51 | 64 |

## With header context and a multilingual encoder

The year in this report is a **column heading**, not part of a row, so nothing in
the row can match "2025". Indexing each row together with its table header — the
same fix that helped the English pipeline — changes the picture:

| arm | before | after |
|---|---|---|
| BM25 (bigrams) | 0.20 | **0.60** |
| dense (`BAAI/bge-m3`, 1024 dims) | 0.13 | **0.47** |
| RRF fusion | 0.27 | **0.73** |

15 Chinese questions, 1,975 table rows. Fusion beats either arm, as in English.

## The agent in Chinese

With the English prompt unchanged and Chinese questions:

| outcome | count (of 15) |
|---|---|
| correct | 7 |
| wrong | 4 |
| rejected | 4 |
| declined | 0 |

So the pipeline *runs* across languages without modification — parsing, retrieval,
tool use and verification all work — but answer quality drops, and the agent
still selects the wrong row about as often as in English paraphrase tests.
