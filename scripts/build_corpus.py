#!/usr/bin/env python3
"""Build the corpus, verify the text layer, and write ground truth.

    python scripts/build_corpus.py [--out build]

Every number this produces is deterministic: the same seed gives the same
digest. The build fails loudly if the PDFs do not contain what the ground truth
claims they contain.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finrag.documents import build_corpus, verify_text_layer  # noqa: E402
from finrag.estate import PERIOD, SEED, build_positions, gold_totals  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build", help="output directory")
    args = ap.parse_args()
    out = Path(args.out)

    corpus = build_corpus(out)
    report = verify_text_layer(corpus, out)

    gt = corpus.as_dict()
    gt["gold_totals"] = gold_totals(build_positions(SEED))
    (out / "ground_truth.json").write_text(json.dumps(gt, indent=2) + "\n")

    n_obs = sum(len(f.observations) for f in corpus.facts.values())
    by_channel: dict[str, int] = {}
    for f in corpus.facts.values():
        for o in f.observations:
            by_channel[o.channel] = by_channel.get(o.channel, 0) + 1

    print(f"documents      {len(corpus.documents)}")
    print(f"pages          {sum(d.pages for d in corpus.documents)}")
    print(f"facts          {len(corpus.facts)}")
    print(f"observations   {n_obs}  {by_channel}")
    print(f"pages verified {report['pages_checked']}")
    print(f"digest         {corpus.digest()}")
    print(f"gold totals    {json.dumps(gt['gold_totals'], sort_keys=True)}")
    print(f"period         {PERIOD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
