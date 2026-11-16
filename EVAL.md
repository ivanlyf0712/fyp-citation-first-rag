# Results — citation-first vs passage-first

- corpus digest `efe21f700744c135`
- 18 probes (`affd5620e3aef4a9`), 36 records

## Outcomes

| pipeline | correct | wrong | declined |
|---|---|---|---|
| passage_first | 9 | 6 | 3 |
| citation_first | 18 | 0 | 0 |

## Citations

| pipeline | answers | mean coverage | full coverage | mean citations |
|---|---|---|---|---|
| passage_first | 9 | 0.64 | 33% | 3.0 |
| citation_first | 12 | 1.00 | 100% | 4.92 |

## Retrieval depth

Citation-first, varying how many units are retrieved. At small k fewer claims can be fully cited, so the pipeline declines more; at large k it can cite everything and never declines. This is the trade the method exposes.

| k units | correct | wrong | declined | mean coverage |
|---|---|---|---|---|
| 3 | 12 | 0 | 6 | 0.41 |
| 5 | 12 | 0 | 6 | 0.48 |
| 10 | 18 | 0 | 0 | 0.67 |
| 20 | 18 | 0 | 0 | 0.67 |
| 40 | 18 | 0 | 0 | 0.67 |

## By probe type

| pipeline / type | correct | wrong | declined |
|---|---|---|---|
| citation_first/cell | 6 | 0 | 0 |
| citation_first/total | 6 | 0 | 0 |
| citation_first/wrong_period | 6 | 0 | 0 |
| passage_first/cell | 3 | 0 | 3 |
| passage_first/total | 0 | 6 | 0 |
| passage_first/wrong_period | 6 | 0 | 0 |

## Reading

`passage_first` answers every question it can by summing whatever appeared on the top pages. On aggregate questions that is a partial sum returned as a total: wrong, confident, and fully cited — the citations are real, they are just not sufficient.

`citation_first` refuses when a required scope is missing from the retrieved units. Its refusals on the unanswerable probes are correct; its refusals on answerable probes are the cost, and they are reported separately.
