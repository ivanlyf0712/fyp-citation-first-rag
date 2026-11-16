# Words vs meaning

23 units, 31 questions, `BAAI/bge-small-en-v1.5` (384 dims).

| qid | question | BM25 rank | embedding rank |
|---|---|---|---|
| Q001 | What was the Group's net profit in 2024? | 4 | 1 |
| Q002 | How much did the bank earn in 2024? | — | 4 |
| Q003 | What was the Group's bottom line for the year? | — | 3 |
| Q004 | How much profit did the Group make after tax? | 7 | 6 |
| Q006 | What was the Net interest income for the Group in 2024? | 4 | 1 |
| Q007 | How much was Net interest income in 2024? | 3 | 1 |
| Q008 | How did Net interest income compare with 2023? | 4 | 1 |
| Q009 | What was the Net non-interest income for the Group in 2024? | 1 | 1 |
| Q010 | How much was Net non-interest income in 2024? | 1 | 1 |
| Q011 | How did Net non-interest income compare with 2023? | 1 | 1 |
| Q012 | What was the Operating income for the Group in 2024? | 4 | 1 |
| Q013 | How much was Operating income in 2024? | 3 | 1 |
| Q014 | How did Operating income compare with 2023? | 2 | 1 |
| Q015 | What was the Operating expenses for the Group in 2024? | 1 | 1 |
| Q016 | How much was Operating expenses in 2024? | 1 | 1 |
| Q017 | How did Operating expenses compare with 2023? | 1 | 1 |
| Q018 | What was the Impairment losses on assets for the Group in 20 | 1 | 1 |
| Q019 | How much was Impairment losses on assets in 2024? | 1 | 1 |
| Q020 | How did Impairment losses on assets compare with 2023? | 1 | 1 |
| Q021 | What was the Profit before taxation for the Group in 2024? | 1 | 1 |
| Q022 | How much was Profit before taxation in 2024? | 1 | 1 |
| Q023 | How did Profit before taxation compare with 2023? | 1 | 1 |
| Q024 | What was the Income tax expense for the Group in 2024? | 1 | 1 |
| Q025 | How much was Income tax expense in 2024? | 1 | 1 |
| Q026 | How did Income tax expense compare with 2023? | 1 | 1 |
| Q027 | What was the Net profit for the Group in 2024? | 4 | 1 |
| Q028 | How much was Net profit in 2024? | 3 | 1 |
| Q029 | How did Net profit compare with 2023? | 2 | 1 |
| Q030 | What was the Total comprehensive income for the Group in 202 | 1 | 1 |
| Q031 | How much was Total comprehensive income in 2024? | 1 | 1 |
| Q032 | How did Total comprehensive income compare with 2023? | 1 | 1 |

| arm | Recall@1 | Recall@5 | MRR |
|---|---|---|---|
| BM25 | 0.58 | 0.90 | 0.69 |
| embeddings | 0.90 | 0.97 | 0.93 |

31 questions, one document. Enough to see a gap, not enough to call it stable across filings.
