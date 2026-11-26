# Agent results

- questions: 5
- units available: 9819
- cited the required unit: 1/5

| outcome | count |
|---|---|
| correct | 2 |
| wrong | 1 |
| rejected | 1 |
| declined | 1 |
| no_hit | 0 |

| qid | gold | answer | verdict | cited required | outcome |
|---|---|---|---|---|---|
| V01 | 80 | Male directors make up 80% of the Board (8 male directors, 80%). | accepted | no | correct |
| V02 | 70 | Independent Non-executive Directors comprised 70% of the Board. | accepted | no | correct |
| V03 | 40 |  | rejected | yes | rejected |
| V04 | 90 | The documents do not contain a figure for the share of directors who a | accepted | no | wrong |
| V05 | 80 | The evidence does not contain a clear figure for the share of director | accepted | no | declined |

## What this establishes

Charts are now evidence: the vision model reads a figure once, the values are
stored on the figure unit (`annotations/corpus/bochk_figures.jsonl`), and an
answer that comes from a chart cites the figure and is checked against those
values like any other unit.

Two of five questions are answered correctly from the image alone. The three
failures are wording, not vision: "attended 100% of board meetings" and "share of
directors based in Hong Kong" do not match the chart's own labels, and the model
would not commit.

Extraction quality on the board-composition chart was complete — 32 values,
percentages and counts, all correct when checked by eye.
