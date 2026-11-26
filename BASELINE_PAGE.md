# Baseline — page-image retrieval (CLIP)

**Headline:** 3/14 concept questions and 4/19 paraphrases. Asking CLIP to pick
whole pages does not work on dense financial text — for "net profit" it
retrieved pages 246, 185 and 203.

**Caveat, stated plainly:** CLIP is a generic image encoder, not a document
retriever. A model trained for document images (ColPali/ColQwen) would do better,
and its weights cannot be downloaded here (HF CDN is throttled to ~831 B/s). So
this is a lower bound on the page-image approach, not a fair representative of
the state of the art.

277 pages embedded with `clip-vit-base-patch32`; top-3 pages retrieved per question, answered from their text.

## concept (14 questions)

| correct | wrong | declined |
|---|---|---|
| 3 | 7 | 4 |

| What was the bank's net profit? | pages [246, 185, 203] | declined |
| What was the operating income? | pages [185, 276, 200] | declined |
| What were the operating expenses? | pages [200, 271, 206] | declined |
| What was the cost-to-income ratio? | pages [185, 178, 276] | wrong |
| What was the net interest margin? | pages [263, 185, 201] | correct |
| What was the non-performing loan ratio? | pages [246, 250, 186] | correct |
| What was the provision coverage ratio? | pages [185, 142, 215] | wrong |
| What was the capital adequacy ratio? | pages [219, 268, 66] | correct |
| What were the earnings per share? | pages [185, 187, 189] | declined |
| What were the total assets? | pages [219, 193, 195] | wrong |
| What were the loans and advances to customers? | pages [183, 185, 188] | wrong |
| What were the customer deposits? | pages [183, 185, 206] | wrong |
| What was the return on average equity? | pages [219, 193, 276] | wrong |
| What was the impairment charge? | pages [269, 264, 272] | wrong |

## paraphrase (19 questions)

| correct | wrong | declined |
|---|---|---|
| 4 | 10 | 5 |

| How much did the bank make from lending after paying fo | pages [179, 209, 203] | declined |
| What did the bank pay for its funding? | pages [203, 195, 193] | wrong |
| What was the bank's fee income before costs? | pages [179, 185, 263] | declined |
| After fees and costs, what did fee business contribute? | pages [250, 171, 263] | correct |
| What did the bank owe in total? | pages [179, 193, 195] | wrong |
| What was the shareholders' stake in the bank? | pages [203, 250, 193] | wrong |
| How much did the bank hold in cash and balances with th | pages [203, 179, 195] | correct |
| How much did the bank lend out after provisions? | pages [203, 193, 195] | wrong |
| How much did customers keep with the bank? | pages [185, 188, 183] | wrong |
| What did the bank earn on its assets, as a percentage? | pages [276, 219, 250] | correct |
| What did the bank earn on shareholders' money, as a per | pages [203, 250, 246] | wrong |
| How much profit did each share earn? | pages [185, 250, 201] | correct |
| What was the bank's interest spread on loans? | pages [193, 203, 179] | declined |
| How much did the bank set aside for credit losses? | pages [276, 185, 184] | wrong |
| What was the workforce cost line? | pages [185, 142, 137] | declined |
| What was the bank's total operating income including fe | pages [193, 203, 195] | declined |
| How much tax did the bank pay on its profit? | pages [185, 179, 203] | wrong |
| What did the bank keep as profit for the year? | pages [203, 201, 246] | wrong |
| What was the total of profit and other gains? | pages [201, 263, 185] | wrong |

