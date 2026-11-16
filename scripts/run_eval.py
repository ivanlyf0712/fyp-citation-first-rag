#!/usr/bin/env python3
"""Run the citation-first and passage-first pipelines over the probe set.

    python scripts/run_eval.py

Writes EVAL.md and build/eval.json. Every figure in the report comes from these
records.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.documents import load_corpus  # noqa: E402
from finrag.evaluate import outcome, summarise  # noqa: E402
from finrag.pipeline import CITATION_FIRST, PASSAGE_FIRST, CitationFirst, run_probe  # noqa: E402
from finrag.probes import build_probes, probe_digest  # noqa: E402


def main() -> int:
    build = Path("build")
    corpus = load_corpus(build)
    probes = build_probes(corpus)
    pipeline = CitationFirst(corpus, build)

    records = []
    for mode in (PASSAGE_FIRST, CITATION_FIRST):
        for probe in probes:
            records.append(run_probe(pipeline, probe, mode) | {"mode": mode})

    # Retrieval depth sweep: at large k the coverage check never binds, so the
    # interesting behaviour is at small k, where citations are scarce.
    sweep = []
    for k in (3, 5, 10, 20, 40):
        pipe = CitationFirst(corpus, build, k_units=k)
        recs = [run_probe(pipe, p, CITATION_FIRST) for p in probes]
        sweep.append({
            "k": k,
            "correct": sum(1 for r in recs if outcome(r) == "correct"),
            "wrong": sum(1 for r in recs if outcome(r) == "wrong"),
            "declined": sum(1 for r in recs if outcome(r) == "declined"),
            "mean_coverage": sum((r["coverage"] or {}).get("ratio", 0.0)
                                 for r in recs) / len(recs),
        })

    (build / "eval.json").write_text(json.dumps(
        {"records": records, "sweep": sweep}, indent=2) + "\n")
    s = summarise(records)

    lines = ["# Results — citation-first vs passage-first", "",
             f"- corpus digest `{corpus.digest()[:16]}`",
             f"- {len(probes)} probes (`{probe_digest(probes)[:16]}`), "
             f"{len(records)} records",
             "", "## Outcomes", "",
             "| pipeline | correct | wrong | declined |", "|---|---|---|---|"]
    for mode in (PASSAGE_FIRST, CITATION_FIRST):
        o = s["outcomes"].get(mode, {})
        lines.append(f"| {mode} | {o.get('correct', 0)} | {o.get('wrong', 0)} | "
                     f"{o.get('declined', 0)} |")

    lines += ["", "## Citations", "",
              "| pipeline | answers | mean coverage | full coverage | mean citations |",
              "|---|---|---|---|---|"]
    for mode in (PASSAGE_FIRST, CITATION_FIRST):
        c = s["citations"].get(mode, {})
        lines.append(f"| {mode} | {c.get('n', 0)} | {c.get('mean_coverage', 0):.2f} | "
                     f"{c.get('full_coverage', 0):.0%} | {c.get('mean_citations', 0)} |")

    by_type: dict[str, dict[str, int]] = {}
    for r in records:
        key = f"{r['mode']}/{r['type']}"
        by_type.setdefault(key, {"correct": 0, "wrong": 0, "declined": 0})
        by_type[key][{"correct": "correct", "wrong": "wrong",
                      "declined": "declined"}[
            "correct" if (r["gold"] is not None and r["status"] == "answered"
                          and r["value"] == r["gold"]) or
            (r["gold"] is None and r["status"] in ("refused", "not_found"))
            else ("wrong" if r["status"] == "answered" else "declined")]] += 1

    lines += ["", "## Retrieval depth", "",
              "Citation-first, varying how many units are retrieved. At small k "
              "fewer claims can be fully cited, so the pipeline declines more; at "
              "large k it can cite everything and never declines. This is the "
              "trade the method exposes.", "",
              "| k units | correct | wrong | declined | mean coverage |",
              "|---|---|---|---|---|"]
    for row in sweep:
        lines.append(f"| {row['k']} | {row['correct']} | {row['wrong']} | "
                     f"{row['declined']} | {row['mean_coverage']:.2f} |")

    lines += ["", "## By probe type", "",
              "| pipeline / type | correct | wrong | declined |", "|---|---|---|---|"]
    for key in sorted(by_type):
        v = by_type[key]
        lines.append(f"| {key} | {v['correct']} | {v['wrong']} | {v['declined']} |")

    lines += ["", "## Reading", "",
              "`passage_first` answers every question it can by summing whatever "
              "appeared on the top pages. On aggregate questions that is a partial "
              "sum returned as a total: wrong, confident, and fully cited — the "
              "citations are real, they are just not sufficient.",
              "",
              "`citation_first` refuses when a required scope is missing from the "
              "retrieved units. Its refusals on the unanswerable probes are correct; "
              "its refusals on answerable probes are the cost, and they are reported "
              "separately."]

    Path("EVAL.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
