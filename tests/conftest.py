"""Shared fixtures.

The corpus is built once per session into a temporary directory: it is the most
expensive thing in the suite, and every test reads the same one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    from finrag.documents import build_corpus, verify_text_layer

    out = tmp_path_factory.mktemp("corpus")
    corpus = build_corpus(out)
    report = verify_text_layer(corpus, out)
    return corpus, out, report


@pytest.fixture(scope="session")
def corpus(built):
    return built[0]


@pytest.fixture(scope="session")
def corpus_dir(built):
    return built[1]


@pytest.fixture(scope="session")
def graph(corpus):
    from finrag.graph import Graph

    return Graph.from_corpus(corpus)
