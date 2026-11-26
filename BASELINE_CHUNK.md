# Baseline — chunk RAG, no verification

**Headline:** on ordinary questions the baseline is competitive (12/14 concept,
9/19 paraphrase). With the evidence removed it shows **7 confident wrong
answers**, where the citation-first system shows 2 and refuses the rest. That is
what verification buys.

1366 text chunks (700 chars, 120 overlap), top-5 after rerank, same model and questions as the citation-first runs.

## concept (14 questions)

| correct | wrong | declined | answers with a number absent from the passages |
|---|---|---|---|
| 12 | 2 | 0 | **0** |

| What was the bank's net profit? | 5,255,815 | correct |  |
| What was the operating income? | 25,481,589 | correct |  |
| What were the operating expenses? | -10,488,740 | correct |  |
| What was the cost-to-income ratio? | 39 | correct |  |
| What was the net interest margin? | 1 | correct |  |
| What was the non-performing loan ratio? | 2 | correct |  |
| What was the provision coverage ratio? | 155 | correct |  |
| What was the capital adequacy ratio? | 12 | correct |  |
| What were the earnings per share? | 0 | correct |  |
| What were the total assets? | 1,843,842,128 | correct |  |
| What were the loans and advances to customers? | 936,490,691 | correct |  |
| What were the customer deposits? | 1,046,088,795 | correct |  |
| What was the return on average equity? | 4 | wrong |  |
| What was the impairment charge? | -9,659,819 | wrong |  |

## paraphrase (19 questions)

| correct | wrong | declined | answers with a number absent from the passages |
|---|---|---|---|
| 9 | 10 | 0 | **0** |

| How much did the bank make from lending after paying fo | 15,542,470 | wrong |  |
| What did the bank pay for its funding? | 510,692 | wrong |  |
| What was the bank's fee income before costs? | 3,995,271 | correct |  |
| After fees and costs, what did fee business contribute? | 2,974,059 | correct |  |
| What did the bank owe in total? | 1,733,717,300 | correct |  |
| What was the shareholders' stake in the bank? | 110,124,828 | wrong |  |
| How much did the bank hold in cash and balances with th | 148,162,149 | correct |  |
| How much did the bank lend out after provisions? | 936,490,691 | wrong |  |
| How much did customers keep with the bank? | 1,046,088,795 | wrong |  |
| What did the bank earn on its assets, as a percentage? | 0 | correct |  |
| What did the bank earn on shareholders' money, as a per | 4 | correct |  |
| How much profit did each share earn? | 0 | correct |  |
| What was the bank's interest spread on loans? | 1 | wrong |  |
| How much did the bank set aside for credit losses? | -9,659,819 | wrong |  |
| What was the workforce cost line? | 5,954,876 | correct |  |
| What was the bank's total operating income including fe | 25,481,589 | wrong |  |
| How much tax did the bank pay on its profit? | -77,215 | correct |  |
| What did the bank keep as profit for the year? | 5,255,815 | wrong |  |
| What was the total of profit and other gains? | 5,675,967 | wrong |  |


## Evidence removed (14 concept questions)

Every chunk containing the answer deleted first. The citation-first system refuses 12 of 14 here.

| correct | wrong | declined |
|---|---|---|
| 3 | 7 | 4 |

| What was the bank's net profit? | 5,255,815 | correct |
| What was the operating income? | 25,481,589 | correct |
| What were the operating expenses? | -10,488,740 | correct |
| What was the cost-to-income ratio? | 39 | wrong |
| What was the net interest margin? | 1 | declined |
| What was the non-performing loan ratio? | 2 | declined |
| What was the provision coverage ratio? | 155 | wrong |
| What was the capital adequacy ratio? | 12 | wrong |
| What were the earnings per share? | 0 | declined |
| What were the total assets? | 1,843,842,128 | wrong |
| What were the loans and advances to customers? | 936,490,691 | wrong |
| What were the customer deposits? | 1,046,088,795 | wrong |
| What was the return on average equity? | 4 | declined |
| What was the impairment charge? | -9,659,819 | wrong |
