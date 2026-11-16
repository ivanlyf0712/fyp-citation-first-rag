"""Append-only annotation files.

Two JSONL files, as agreed:

* ``annotations/units.jsonl``     every accepted unit, one per line;
* ``annotations/questions.jsonl`` probes that reference unit ids.

Appending immediately means a crash or a closed browser costs at most the last
click, and the file is diffable and reviewable afterwards. Writes are
line-buffered and flushed, and duplicates are rejected by ``unit_id`` so
double-clicking a button cannot corrupt the set.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()


def read_all(path: Path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def accepted_ids(path: Path) -> set[str]:
    return {r["unit_id"] for r in read_all(path)}


def accept_unit(path: Path, unit: dict[str, Any]) -> bool:
    """Append unless already present. Returns whether it was written."""
    if unit["unit_id"] in accepted_ids(path):
        return False
    record = dict(unit)
    record["verified"] = True
    record["accepted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _append(path, record)
    return True


def add_question(path: Path, qid: str, question: str, gold_value: float | None,
                 required_units: Iterable[str], doc: str) -> None:
    _append(path, {
        "qid": qid, "question": question, "gold_value": gold_value,
        "required_units": list(required_units), "doc": doc,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


def archive_files(paths: list[Path], archive_dir: Path) -> Path:
    """Move annotation files into a timestamped folder.

    Reset archives rather than deletes: an annotation set is work, and a wrong
    click should cost a `mv` back, not the afternoon.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = Path(archive_dir) / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if Path(path).exists():
            shutil.move(str(path), str(dest / Path(path).name))
    return dest


def delete_unit(path: Path, unit_id: str) -> bool:
    """Remove one accepted unit. Returns whether anything was removed."""
    rows = read_all(path)
    keep = [r for r in rows if r["unit_id"] != unit_id]
    if len(keep) == len(rows):
        return False
    Path(path).write_text("\n".join(json.dumps(r, sort_keys=True) for r in keep) + "\n")
    return True
