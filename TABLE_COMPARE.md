# Table extraction on a real filing

`0003_HK-China-Gas_ESG-Report_2025.pdf`, first 20 pages.

| tool | tables | cells | mean cells/table | time |
|---|---|---|---|---|
| PyMuPDF `find_tables` | 7 | 576 | 82 | 6.5s |
| Docling | 12 | 253 | 21 | 57.8s |

Tables detected by both (IoU ≥ 0.5): **7** of 7 found by PyMuPDF.

## PyMuPDF — first table

page 17, 7×7 cells

`Risk
Categories | PotentialImpacts | `

## Docling — first table

page 2, 8×2

`About This Report | 02`
