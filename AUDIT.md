# Audit — are the questions fair?

Two of the three persistently failing paraphrase questions turned out to be
ill-posed, not badly answered. The failure was in the instrument.

## Verdicts

| qid | question | verdict | why |
|---|---|---|---|
| H01 | "After everything is paid, how much did the bank actually make that year?" | **ambiguous** | the bank reports *net profit* (5,255,815) and *profit attributable to ordinary shareholders* after perpetual-bond coupons (4,305,815); both answer "what it made" |
| H02 | "What did it cost to run the business?" | fair | operating expenses |
| H03 | "How much did the group earn from its core lending activity?" | borderline | net interest income vs interest income from loans; kept, flagged |
| H04 | "How much was set aside for loans and assets that went bad?" | fair | impairment losses |
| H05 | "How much did the government take in tax?" | fair | income tax expense |
| H06 | "What was the profit before the tax charge?" | fair | profit before taxation |
| H07 | "What was the total of all earnings, including items outside profit?" | fair | total comprehensive income |
| H08 | "What was the income before costs were deducted?" | **ambiguous** | operating income vs net interest income |
| H09 | "How much did fee and other non-lending activities bring in?" | **ambiguous** | net fee income (2,974,059) vs net non-interest income (9,939,119) |
| H10 | "What was the profit before any tax was deducted?" | fair | profit before taxation |

## Corrected numbers

Well-posed set: 7 questions (H02, H04, H05, H06, H07, H10, plus H03 marked
borderline and retained).

| run | all 10 | well-posed 7 |
|---|---|---|
| 1 | 6 | 6/7 = 0.86 |
| 2 | 7 | 7/7 = 1.00 |
| 3 | 5 | 4/7 = 0.57 |
| mean | 6.0 (0.60) | **5.67 (0.81)** |

## What this says

Half of the gap between 0.60 and 0.90 was the question set, not the system.
Reporting only 0.60 would understate the system; reporting only 0.81 would hide
that the author writes ambiguous questions. Both belong in the write-up, with the
verdict table above.

## The system-side lesson

H01 exposes a scoring weakness worth fixing properly: the model stated two real
numbers from two adjacent rows, and the check accepted both because both are in
the cited quotes. A label-alignment rule — prefer the number whose row label
matches the question's metric — is the deterministic fix, and it is the same
mechanism as the scope weighting.
