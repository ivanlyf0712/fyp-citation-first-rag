# Baseline — same agent, verification off

Identical units, retrieval, tools and model; unsupported answers are shown
instead of withheld.

| set | correct | wrong | declined | unsupported answers shown |
|---|---|---|---|---|
| concept (14) | 10 | 2 | 2 | **0** |
| paraphrase (19) | 10 | 6 | 3 | **0** |

**Reading:** on ordinary questions the checks almost never fire — the model
grounds itself in the quotes it cites, so switching enforcement off changes
little. Their value appears only when the evidence is insufficient: there the
chunk baseline emits 7 confident wrong answers, and this agent with checks emits
2 while refusing the rest.

Identical units, retrieval, tools and model. The only change is that unsupported answers are shown rather than withheld.

## concept (14 questions)

| correct | wrong | declined | shown despite unsupported numbers |
|---|---|---|---|
| 10 | 2 | 2 | **0** |

| What was the bank's net profit? | 5,255,815 | correct |  |
| What was the operating income? | 25,481,589 | declined |  |
| What were the operating expenses? | -10,488,740 | wrong |  |
| What was the cost-to-income ratio? | 39 | correct |  |
| What was the net interest margin? | 1 | correct |  |
| What was the non-performing loan ratio? | 2 | correct |  |
| What was the provision coverage ratio? | 155 | correct |  |
| What was the capital adequacy ratio? | 12 | correct |  |
| What were the earnings per share? | 0 | correct |  |
| What were the total assets? | 1,843,842,128 | correct |  |
| What were the loans and advances to customers? | 936,490,691 | declined |  |
| What were the customer deposits? | 1,046,088,795 | wrong |  |
| What was the return on average equity? | 4 | correct |  |
| What was the impairment charge? | -9,659,819 | correct |  |

## paraphrase (19 questions)

| correct | wrong | declined | shown despite unsupported numbers |
|---|---|---|---|
| 10 | 6 | 3 | **0** |

| How much did the bank make from lending after paying fo | 15,542,470 | correct |  |
| What did the bank pay for its funding? | 510,692 | wrong |  |
| What was the bank's fee income before costs? | 3,995,271 | wrong |  |
| After fees and costs, what did fee business contribute? | 2,974,059 | correct |  |
| What did the bank owe in total? | 1,733,717,300 | correct |  |
| What was the shareholders' stake in the bank? | 110,124,828 | wrong |  |
| How much did the bank hold in cash and balances with th | 148,162,149 | correct |  |
| How much did the bank lend out after provisions? | 936,490,691 | wrong |  |
| How much did customers keep with the bank? | 1,046,088,795 | wrong |  |
| What did the bank earn on its assets, as a percentage? | 0 | correct |  |
| What did the bank earn on shareholders' money, as a per | 4 | correct |  |
| How much profit did each share earn? | 0 | correct |  |
| What was the bank's interest spread on loans? | 1 | correct |  |
| How much did the bank set aside for credit losses? | -9,659,819 | declined |  |
| What was the workforce cost line? | 5,954,876 | wrong |  |
| What was the bank's total operating income including fe | 25,481,589 | declined |  |
| How much tax did the bank pay on its profit? | -77,215 | correct |  |
| What did the bank keep as profit for the year? | 5,255,815 | correct |  |
| What was the total of profit and other gains? | 5,675,967 | declined |  |

