#!/bin/bash
# One-command demo: parse (if needed), then run two questions.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"; [ -x "$PY" ] || PY=".venv314/bin/python"; [ -x "$PY" ] || PY="python3"

if [ ! -f annotations/corpus/units.jsonl ]; then
  echo "Building the unit corpus (one page ~5 s)…"
  "$PY" scripts/build_unit_corpus.py --pdf samples/bohai_bank_annual_2024.pdf \
      --out annotations/corpus/units.jsonl
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "DEEPSEEK_API_KEY is not set."
  echo "  export DEEPSEEK_API_KEY=sk-...   then re-run scripts/demo.sh"
  exit 1
fi

"$PY" scripts/demo_cli.py
