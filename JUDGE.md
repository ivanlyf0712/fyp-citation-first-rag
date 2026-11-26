# LLM as judge

A second model grades each answer against the question, the gold value and the
quotes the answer cites. It is not ground truth — it is a second opinion.

**Result: the judge agrees with exact-number scoring 0.93 (kappa 0.81) on the
concept set and 0.95 (kappa 0.87) on paraphrases**, and calls every answer
faithful to its citations. So the deterministic scorer is not an artefact of its
own rule, and the errors are selection, not grounding.

Getting there took two fixes to the judge's input: gold values rounded to
integers (`1.31` → `1`) and scientific notation (`2.5e+07`) both caused false
disagreements. Judges need the same care as any other measurement instrument.

## concept (14 questions)

- agreement on correctness: **0.93** (kappa 0.81)
- judge says faithful to citations: 14/14
- deterministic correct: 11
- judge correct: 10

| B10 | deterministic True | judge False | The answer states RMB1,843,842,128 thousand, which is 1000x the reference value  |

## paraphrase (19 questions)

- agreement on correctness: **0.95** (kappa 0.87)
- judge says faithful to citations: 19/19
- deterministic correct: 13
- judge correct: 14

| P17 | deterministic False | judge True | RMB77 million matches -77,215.00 (rounded, sign/unit convention), and both figur |

