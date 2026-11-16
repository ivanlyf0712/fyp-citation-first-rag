#!/bin/bash
# Rebuild every table in RESULTS.md from scratch.
set -euo pipefail
cd "$(dirname "$0")/.."

export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:?set the key first}"

python scripts/build_unit_corpus.py            # 277 pages, cached per page
for i in 1 2 3; do
  python scripts/score_agent.py --units annotations/corpus/units.jsonl \
      --semantic --rerank --sections --workers 4 \
      --questions annotations/questions_blind.jsonl --out results/frozen/concept_$i.md
  python scripts/score_agent.py --units annotations/corpus/units.jsonl \
      --semantic --rerank --sections --workers 4 \
      --questions annotations/questions_hard.jsonl --out results/frozen/paraphrase_$i.md
done
python scripts/restriction_eval.py
python -m pytest -q
