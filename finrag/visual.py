"""Visual retrieval over page images.

The corpus already stores each page as a raster, but until now nothing indexed
them: figures were read through the generator's ground truth. This module adds a
real text-to-image index, so a query is matched against the *picture* of a page
rather than against text extracted from it.

The model is CLIP ViT-B/32 — deliberately the generic multimodal embedding rather
than a document-specific retriever. CLIP is the baseline that ColPali was built
to beat: it embeds a whole page into one vector at 224 px, so it sees layout and
colour but loses the small print that financial figures live in. Measuring that
weakness on this corpus is the point; the expected result is that CLIP ranks
pages worse than BM25, which is exactly why the document-specific models exist.

Reference: Radford et al. (2021), *Learning Transferable Visual Models From
Natural Language Supervision*; contrast ColPali (Faysse et al., 2024).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_ID = "openai/clip-vit-base-patch32"


def _as_tensor(out):
    """Transformers 5 returns a model-output object rather than a tensor."""
    for attr in ("image_embeds", "text_embeds", "pooler_output"):
        value = getattr(out, attr, None)
        if value is not None and hasattr(value, "norm"):
            return value
    if isinstance(out, (tuple, list)):
        return out[0]
    return out


@dataclass(frozen=True)
class PageHit:
    doc_id: str
    page: int
    score: float


def render_pages(corpus, out_dir: Path, dpi: int = 110) -> list[tuple[str, int, Image.Image]]:
    pages: list[tuple[str, int, Image.Image]] = []
    for doc in corpus.documents:
        with pymupdf.open(Path(out_dir) / doc.path) as pdf:
            for number, page in enumerate(pdf, start=1):
                pix = page.get_pixmap(dpi=dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                pages.append((doc.doc_id, number, img))
    return pages


class ClipIndex:
    """A frozen CLIP image index with a text query head."""

    def __init__(self, device: str | None = None) -> None:
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model = CLIPModel.from_pretrained(MODEL_ID).to(self.device).eval()
        self.processor = CLIPProcessor.from_pretrained(MODEL_ID)
        self.keys: list[tuple[str, int]] = []
        self.embeddings: np.ndarray | None = None

    @torch.no_grad()
    def build(self, pages: list[tuple[str, int, Image.Image]],
              batch: int = 16) -> None:
        vectors = []
        for i in range(0, len(pages), batch):
            chunk = pages[i:i + batch]
            inputs = self.processor(images=[p[2] for p in chunk], return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = _as_tensor(self.model.get_image_features(**inputs))
            feats = feats / feats.norm(dim=-1, keepdim=True)
            vectors.append(feats.cpu().numpy())
        self.embeddings = np.vstack(vectors)
        self.keys = [(doc, page) for doc, page, _ in pages]

    @torch.no_grad()
    def search(self, query: str, k: int = 10) -> list[PageHit]:
        if self.embeddings is None:
            raise RuntimeError("index not built")
        inputs = self.processor(text=[query], return_tensors="pt", padding=True)
        inputs = {key: v.to(self.device) for key, v in inputs.items()}
        q = _as_tensor(self.model.get_text_features(**inputs))
        q = (q / q.norm(dim=-1, keepdim=True)).cpu().numpy()[0]
        scores = self.embeddings @ q
        order = np.argsort(-scores)[:k]
        return [PageHit(self.keys[i][0], self.keys[i][1], float(scores[i]))
                for i in order]

    def ranked_docs(self, query: str, k: int = 10) -> list[str]:
        out: list[str] = []
        for hit in self.search(query, k=k):
            if hit.doc_id not in out:
                out.append(hit.doc_id)
        return out

    # -- persistence -------------------------------------------------------
    def save(self, path: Path) -> None:
        np.savez_compressed(path, embeddings=self.embeddings,
                            keys=np.array(self.keys, dtype=object), allow_pickle=True)

    def load(self, path: Path) -> None:
        data = np.load(path, allow_pickle=True)
        self.embeddings = data["embeddings"]
        self.keys = [tuple(x) for x in data["keys"]]
