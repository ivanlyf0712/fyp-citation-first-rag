# Does the unit builder generalise?

One page from three structurally different filings, parsed with and without the header/footer filter.

| document | page | units before | after | dropped | dropped with a number | table units | row units |
|---|---|---|---|---|---|---|---|
| Bohai Bank annual report | 18 | 41 | 37 | 4 | **2** | 10 | 10 |
| Towngas ESG report | 17 | 49 | 12 | 37 | **4** | 5 | 5 |
| HKEX ESG report | 12 | 50 | 47 | 3 | **2** | 0 | 0 |

## Reading

`dropped with a number` is the number that matters: a unit containing a figure is content, not furniture.

- Documents where the band removed numeric content: **3 of 3**.
- It removed 37 of 49 units from one ESG page, so the threshold is fitted to the bank report's header position, not to documents.
- Verdict: **rejected**. It is disabled by default in `parse_pdf`.

The robust version is not positional: detect lines that repeat across pages (the running header and footer) and drop those, which adapts to each layout instead of assuming one.
