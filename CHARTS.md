# Agent results

- questions: 5
- units available: 9819
- cited the required unit: 2/5

| outcome | count |
|---|---|
| correct | 3 |
| wrong | 0 |
| rejected | 1 |
| declined | 1 |
| no_hit | 0 |

| qid | gold | answer | verdict | cited required | outcome |
|---|---|---|---|---|---|
| V01 | 80 | Male directors make up 80% of the Board (8 of 10 directors). | accepted | yes | correct |
| V02 | 70 | Independent Non-executive Directors comprised 70% of the Board. | accepted | no | correct |
| V03 | 40 | 40% of directors fall in the 56-65 age group. | accepted | yes | correct |
| V04 | 90 |  | rejected | no | rejected |
| V05 | 80 |  | declined | no | declined |

## Result after wording and format fixes

Three runs, same five questions, enriched corpus:

| run | correct | wrong | rejected | declined |
|---|---|---|---|---|
| 1 | 3 | 0 | 1 | 1 |
| 2 | 3 | 0 | 1 | 1 |
| 3 | 3 | 1 | 0 | 1 |

**Stable at 3/5.** The two failures:

- **V04 attendance (90).** Ambiguous in this document: the chart says 90% of
  directors had 100% attendance, while a sentence on the page says *"Average
  Attendance Rate: 100%"*. A reader could answer either. Audited as ambiguous,
  like the three text questions in [AUDIT.md](AUDIT.md).
- **V05 Hong Kong (80).** A fair question, genuinely missed — the model declined
  rather than read the chart.

On the four fair questions: **3/4 = 0.75**.

## Fixes that came out of this

- `answer_numbers` no longer reads an age range ("56-65") as two claimed numbers;
- support accepts numbers that appear in a quoted chart's text, not only its
  parsed values;
- figure quotes are grouped by panel, which was worth one extra correct answer
  over a flat list.
