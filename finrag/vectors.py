"""Unit embeddings: the "meaning" arm of retrieval.

Two things matter more than the model choice.

**What gets embedded.** A bare table row (`5,255,815 | 5,080,903 | …`) has almost
no semantic content. Each row is therefore embedded with the header row of its
table prepended, so the vector describes *net profit in 2024*, not five numbers.
Header detection is positional and explained below.

**How it is stored.** One `.npz` per (model, unit-set) plus a JSON manifest.
Vectors are L2-normalised on write, so search is a dot product. The filename
carries the model and a hash of the unit ids: change either and a new file is
written rather than silently contradicting the old one — the same failure mode
that the parse cache already produced twice.

The model is `bge-small-en-v1.5` (384 dims). It is small enough to run on this
machine in seconds and strong enough on English financial prose; `bge-m3` is the
drop-in replacement if the corpus turns bilingual.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

MODEL_ID = "BAAI/bge-small-en-v1.5"

_MODELS: dict[str, object] = {}


def _model(model_id: str):
    """Load once per process. Re-instantiating per query dominated run time."""
    if model_id not in _MODELS:
        from sentence_transformers import SentenceTransformer
        _MODELS[model_id] = SentenceTransformer(model_id)
    return _MODELS[model_id]
VECTOR_VERSION = 1


def unit_contexts(units: Iterable) -> list[tuple[str, str]]:
    """(unit_id, text-to-embed) for each unit, with table headers prepended.

    A table's header is taken to be the topmost row unit on the same page. That
    is a positional assumption, and it is wrong for stacked tables — so it is
    stated here rather than hidden: a page with two tables gives the second
    table's rows the first table's header.
    """
    units = list(units)
    headers: dict[tuple[str, int], str] = {}
    for unit in sorted(units, key=lambda u: (-u.bbox[3], u.bbox[0])):
        if getattr(unit, "source", "") == "docling-row":
            headers.setdefault((unit.doc, unit.page), unit.quote)

    out = []
    for unit in units:
        text = unit.quote
        if getattr(unit, "source", "") == "docling-row":
            header = headers.get((unit.doc, unit.page), "")
            if header and header != unit.quote:
                text = f"{header} :: {unit.quote}"
        out.append((unit.unit_id, text))
    return out


def _fingerprint(unit_ids: list[str]) -> str:
    blob = "|".join(unit_ids).encode()
    return hashlib.sha1(blob).hexdigest()[:10]


@dataclass
class UnitIndex:
    unit_ids: list[str]
    vectors: np.ndarray          # N x D, L2-normalised
    model_id: str = MODEL_ID

    def __post_init__(self) -> None:
        self._rows = {uid: i for i, uid in enumerate(self.unit_ids)}

    # -- construction ------------------------------------------------------
    @classmethod
    def build(cls, units: Iterable, model_id: str = MODEL_ID, batch: int = 32,
              device: str | None = None) -> "UnitIndex":
        pairs = unit_contexts(units)
        model = _model(model_id)
        texts = [text for _uid, text in pairs]
        matrix = model.encode(texts, batch_size=batch, convert_to_numpy=True,
                              normalize_embeddings=True, show_progress_bar=False)
        return cls(unit_ids=[uid for uid, _ in pairs],
                   vectors=matrix.astype(np.float32), model_id=model_id)

    # -- search ------------------------------------------------------------
    def search(self, query: str, k: int = 10, model_id: str | None = None) -> list[tuple[str, float]]:
        model = _model(model_id or self.model_id)
        q = model.encode([query], normalize_embeddings=True,
                         convert_to_numpy=True)[0].astype(np.float32)
        scores = self.vectors @ q
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(self.unit_ids[i], float(scores[i])) for i in top]

    def rank_of(self, unit_id: str, query: str, model_id: str | None = None) -> int | None:
        model = _model(model_id or self.model_id)
        q = model.encode([query], normalize_embeddings=True,
                         convert_to_numpy=True)[0].astype(np.float32)
        scores = self.vectors @ q
        order = np.argsort(-scores)
        for rank, i in enumerate(order, start=1):
            if self.unit_ids[i] == unit_id:
                return rank
        return None

    # -- persistence -------------------------------------------------------
    def save(self, directory: Path, source: dict | None = None) -> tuple[Path, Path]:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{self.model_id.split('/')[-1]}__v{VECTOR_VERSION}__{_fingerprint(self.unit_ids)}"
        npz = directory / f"{stem}.npz"
        np.savez_compressed(npz, vectors=self.vectors,
                            unit_ids=np.array(self.unit_ids))
        manifest = directory / f"{stem}.json"
        manifest.write_text(json.dumps({
            "model": self.model_id, "dim": int(self.vectors.shape[1]),
            "count": len(self.unit_ids), "vector_version": VECTOR_VERSION,
            "unit_fingerprint": _fingerprint(self.unit_ids),
            "source": source or {},
        }, indent=2) + "\n")
        return npz, manifest

    @classmethod
    def load(cls, npz: Path) -> "UnitIndex":
        data = np.load(npz, allow_pickle=True)
        return cls(unit_ids=[str(x) for x in data["unit_ids"]],
                   vectors=data["vectors"])
