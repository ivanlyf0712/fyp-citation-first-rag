"""Tests for the BM25 retrieval arm."""

from __future__ import annotations

from finrag.retrieve import Bm25Index, Chunk, tokenize


def make_index() -> Bm25Index:
    idx = Bm25Index()
    idx.add(Chunk("D-1", 1, "Credit memo Harbour Finance HK credit desk exposure 120 million"))
    idx.add(Chunk("D-2", 1, "Credit memo Kowloon Commerce SG treasury desk exposure 55 million"))
    idx.add(Chunk("D-3", 1, "Policy extract aggregation policy for the HK entity"))
    idx.finalize()
    return idx


def test_tokenizer_drops_stopwords_and_short_tokens():
    assert tokenize("What is the total exposure for Harbour Finance?") == [
        "total", "exposure", "harbour", "finance"]


def test_ranking_prefers_the_matching_page():
    idx = make_index()
    hits = idx.search("Harbour Finance exposure", k=3)
    assert hits and hits[0][0] == "D-1"
    assert all(score > 0 for _d, _p, score in hits)


def test_documents_are_deduplicated():
    idx = make_index()
    idx.add(Chunk("D-1", 2, "Harbour Finance continued exposure 120"))
    idx.finalize()
    ranked = idx.ranked_docs("Harbour Finance exposure", k=5)
    assert ranked.count("D-1") == 1


def test_no_match_returns_nothing():
    idx = make_index()
    assert idx.search("zebra quantum", k=5) == []


def test_allowed_filter_is_respected():
    idx = make_index()
    hits = idx.search("exposure", k=5, allowed={"D-2"})
    assert {d for d, _p, _s in hits} == {"D-2"}
