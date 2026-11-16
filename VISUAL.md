# Visual retrieval — CLIP over page images

CLIP ViT-B/32, one vector per page at 224 px, cosine similarity against a text query. Same probes, same gold evidence, same k = 10 as the lexical arm.

| arm | probe type | n | Recall@10 | nDCG@10 | MRR |
|---|---|---|---|---|---|
| BM25 (text) | cell | 6 | 1.000 | 0.609 | 0.492 |
| BM25 (text) | total | 6 | 0.983 | 0.989 | 1.000 |
| BM25 (text) | all | 12 | 0.992 | 0.799 | 0.746 |
| CLIP (image) | cell | 6 | 0.500 | 0.267 | 0.204 |
| CLIP (image) | total | 6 | 0.537 | 0.571 | 0.722 |
| CLIP (image) | all | 12 | 0.519 | 0.419 | 0.463 |

## Reading

CLIP embeds the whole page into a single vector, so it can match the *kind* of page — a credit memo, a chart — but not the specific figure inside it. On a corpus where every page looks alike and the answer turns on one number, that is the wrong granularity, and the numbers above should be read as the cost of it.

This is the gap ColPali was built to close: late interaction over page patches preserves the local detail that a single page vector averages away. Adding it, and comparing, is the next rung.
