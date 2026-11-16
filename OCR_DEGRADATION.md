# OCR degradation

Text pages rendered at several resolutions and re-read by Tesseract, then compared against the PDF text layer — the "perfect extraction" condition.

| dpi | pages | numeric recall | pages with every number | mean CER |
|---|---|---|---|---|
| 150 | 56 | 100.0% | 100.0% | 0.049 |
| 100 | 56 | 100.0% | 100.0% | 0.087 |
| 72 | 56 | 80.4% | 80.4% | 0.188 |

## Reading

Numeric recall is the number that matters: a lost figure is a lost fact, and the completeness check would then act on evidence the system never had. Character error rate is the general measure of how much of the text changed.

The curve is the finding. At 150 and 100 dpi every numeric fact survives while roughly one character in twenty changes — OCR damages prose, not figures. Degradation only bites at 72 dpi, where a fifth of the pages lose at least one number. So the perfect-extraction assumption is safe for this layout at normal scan quality, and the main results can be read as an upper bound only below it.

This experiment does **not** change the pipeline; it prices the assumption.

## Worst pages at 72 dpi

| document | page | numbers found | CER |
|---|---|---|---|
| D-027 | 1 | 0/1 | 0.128 |
| D-021 | 1 | 0/1 | 0.159 |
| D-009 | 1 | 0/1 | 0.160 |
| D-005 | 1 | 0/1 | 0.180 |
| D-017 | 1 | 0/1 | 0.184 |
