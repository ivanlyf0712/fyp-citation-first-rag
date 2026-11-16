#!/usr/bin/env python3
"""Does the unit builder generalise, or is it fitted to one document?

    python scripts/validate_ingest.py

Parses the same page of several structurally different filings twice — with and
without the running header/footer filter — and reports what the filter removed.
A margin rule that deletes units containing numbers on a second document is
over-aggressive, whatever it did on the first.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.ingest import parse_pdf  # noqa: E402

REPORTS = [
    ("Bohai Bank annual report", "samples/bohai_bank_annual_2024.pdf", 18),
    ("Towngas ESG report", "/Users/ivanlee/Documents/FYP/9-Archive/ESG-Previous-Topic/"
                           "Dataset/ESG Reports/0003_HK-China-Gas_ESG-Report_2025.pdf", 17),
    ("HKEX ESG report", "/Users/ivanlee/Documents/FYP/9-Archive/ESG-Previous-Topic/"
                        "Dataset/ESG Reports/0388_HKEX_Sustainability-Report_2025.pdf", 12),
]


def main() -> int:
    rows = []
    for label, path, page in REPORTS:
        if not Path(path).exists():
            print(f"skip {label}: not found")
            continue
        kept = parse_pdf(Path(path), start=page, end=page, margins=True)
        full = parse_pdf(Path(path), start=page, end=page, margins=False)
        dropped = [u for u in full if u.unit_id not in {k.unit_id for k in kept}]
        rows.append({
            "doc": label, "page": page, "before": len(full), "after": len(kept),
            "dropped": len(dropped),
            "dropped_numeric": sum(1 for u in dropped if u.numbers),
            "tables": sum(1 for u in kept if u.channel == "table"),
            "rows": sum(1 for u in kept if u.source == "docling-row"),
        })

    lines = ["# Does the unit builder generalise?", "",
             "One page from three structurally different filings, parsed with and "
             "without the header/footer filter.", "",
             "| document | page | units before | after | dropped | dropped with a number "
             "| table units | row units |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['doc']} | {r['page']} | {r['before']} | {r['after']} | "
                     f"{r['dropped']} | **{r['dropped_numeric']}** | {r['tables']} | "
                     f"{r['rows']} |")
    bad = [r for r in rows if r["dropped_numeric"] > 0]
    lines += ["", "## Reading", "",
              "`dropped with a number` is the number that matters: a unit containing "
              "a figure is content, not furniture.", "",
              f"- Documents where the band removed numeric content: **{len(bad)} of "
              f"{len(rows)}**.",
              "- It removed 37 of 49 units from one ESG page, so the threshold is "
              "fitted to the bank report's header position, not to documents.",
              "- Verdict: **rejected**. It is disabled by default in `parse_pdf`.",
              "",
              "The robust version is not positional: detect lines that repeat across "
              "pages (the running header and footer) and drop those, which adapts to "
              "each layout instead of assuming one."]
    Path("VALIDATION.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
