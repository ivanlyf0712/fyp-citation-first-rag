"""Agent tests driven by a stub client — no network, no key."""

from __future__ import annotations

from types import SimpleNamespace

from finrag.agent_rag import Tools, run, score_answer, verify_answer
from finrag.llm import StubClient


def unit(uid: str, quote: str, numbers: list[float], page: int = 18,
         top: float = 0.0):
    return SimpleNamespace(unit_id=uid, doc="a.pdf", page=page, channel="table",
                           quote=quote, numbers=tuple(numbers),
                           bbox=(0.0, top, 100.0, top + 8.0), source="docling-row")


UNITS = [
    unit("U:head", "2024 | 2023 | Change | Increase (%)", [], top=100.0),
    unit("U:row", "Net profit | 5,255,815 | 5,080,903 | 174,912",
         [5255815.0, 5080903.0], top=90.0),
    unit("U:txt", "The Group recorded a net profit of RMB5,256 million",
         [5256.0], top=50.0),
]
BY_ID = {u.unit_id: u for u in UNITS}


def test_tools_find_the_row_and_read_it():
    tools = Tools(UNITS)
    hits = tools.search_bm25("net profit", k=5)
    assert hits and hits[0]["unit_id"] in {"U:row", "U:txt"}
    assert tools.call("read_unit", {"unit_id": "U:nope"})["unit"]["error"]


def test_supported_answer_is_accepted():
    v = verify_answer("Net profit was RMB5,255,815 thousand in 2024.", ["U:row"], BY_ID)
    assert v["accepted"] and v["status"] == "accepted"


def test_year_is_not_treated_as_a_claim():
    v = verify_answer("In 2024 net profit was 5,255,815 thousand.", ["U:row"], BY_ID)
    assert v["accepted"], v["failures"]


def test_fabricated_number_is_rejected():
    v = verify_answer("Net profit was 817 million.", ["U:row"], BY_ID)
    assert not v["accepted"] and v["status"] == "rejected"


def test_number_without_citation_is_rejected():
    v = verify_answer("Net profit was 5,255,815 thousand.", [], BY_ID)
    assert not v["accepted"]


def test_declining_is_not_a_failure():
    v = verify_answer("I cannot answer from the evidence.", [], BY_ID)
    assert v["status"] == "declined" and v["failures"] == []


def test_loop_uses_a_tool_then_answers():
    client = StubClient(replies=[
        '{"tool": "search_bm25", "query": "net profit", "k": 5}',
        '{"answer": "Net profit was 5,255,815 thousand in 2024.", "citations": ["U:row"]}',
    ])
    result = run("What was net profit?", client, Tools(UNITS))
    assert result["verification"]["accepted"]
    assert result["tool_calls"] == 1 and result["trace"][0]["tool"] == "search_bm25"


def test_loop_rejects_a_fabricated_answer():
    client = StubClient(replies=[
        '{"answer": "Net profit was 817 million.", "citations": ["U:row"]}',
    ])
    result = run("What was net profit?", client, Tools(UNITS))
    assert not result["verification"]["accepted"]


def test_malformed_turn_is_repaired_once():
    client = StubClient(replies=[
        "I will search now.",
        '{"answer": "Net profit was 5,255,815 thousand.", "citations": ["U:row"]}',
    ])
    result = run("What was net profit?", client, Tools(UNITS))
    assert result["verification"]["accepted"]


def test_tool_budget_forces_an_answer():
    replies = ['{"tool": "search_bm25", "query": "net profit"}'] * 3
    replies.append('{"answer": "Net profit was 5,255,815 thousand.", "citations": ["U:row"]}')
    client = StubClient(replies=replies)
    result = run("What was net profit?", client, Tools(UNITS), max_calls=2)
    assert result["verification"]["accepted"]
    assert result["tool_calls"] == 3


def test_scoring_separates_rejection_from_being_wrong():
    good = {"verification": {"status": "accepted", "accepted": True,
                             "numbers": [5255815.0]}}
    assert score_answer(good, 5255815.0) == "correct"
    assert score_answer(good, 999.0) == "wrong"

    rejected = {"verification": {"status": "rejected", "accepted": False,
                                 "numbers": [817.0]}}
    assert score_answer(rejected, 5255815.0) == "rejected"

    declined = {"verification": {"status": "declined", "accepted": False,
                                 "numbers": []}}
    assert score_answer(declined, 5255815.0) == "declined"


def test_comma_formatted_year_is_ignored():
    v = verify_answer("In 2,024 the net profit was 5255815.", ["U:row"], BY_ID)
    assert v["accepted"], v["failures"]


def test_scale_convention_counts_as_correct():
    from finrag.agent_rag import value_matches
    assert value_matches(5256.0, 5255815.0)        # RMB5,256 million vs RMB'000
    assert value_matches(5255815.0, 5255815.0)
    assert not value_matches(5300000.0, 5255815.0)


def test_sign_convention_counts_as_correct():
    from finrag.agent_rag import value_matches
    assert value_matches(10488740.0, -10488740.0)  # "expenses were 10,488,740"


def test_prose_refusal_is_declined_not_wrong():
    result = {"answer": "The evidence does not contain that figure.",
              "verification": {"status": "accepted", "accepted": True,
                               "numbers": []}}
    assert score_answer(result, 5255815.0) == "declined"

    result = {"answer": "The evidence does not contain that figure, though it "
                        "shows 25,481,589 elsewhere.",
              "verification": {"status": "accepted", "accepted": True,
                               "numbers": [25481589.0]}}
    assert score_answer(result, 999.0) == "declined"


def test_only_the_first_number_is_the_claim():
    result = {"answer": "Operating income was 25,481,589 and net profit 5,255,815.",
              "verification": {"status": "accepted", "accepted": True,
                               "numbers": [25481589.0, 5255815.0]}}
    assert score_answer(result, 5255815.0) == "wrong"
    assert score_answer(result, 25481589.0) == "correct"


def test_wrong_column_is_rejected():
    """2023's figure cited as 2024's: supported by the quote, wrong by column."""
    from finrag.agent_rag import verify_answer

    units = {
        "U:row": SimpleNamespace(
            unit_id="U:row", doc="a.pdf", page=18, channel="table",
            quote="Net profit | 5,255,815 | 5,080,903 | 174,912 | 3.44",
            numbers=(5255815.0, 5080903.0, 174912.0, 3.44)),
    }
    headers = {("a.pdf", 18): "2024 | 2023 | Change | Increase (%)"}

    wrong = verify_answer("Net profit was 5,080,903 in 2024.", ["U:row"], units,
                          headers=headers, question="What was net profit in 2024?")
    assert not wrong["accepted"], "the 2023 column must not satisfy a 2024 question"

    right = verify_answer("Net profit was 5,255,815 in 2024.", ["U:row"], units,
                          headers=headers, question="What was net profit in 2024?")
    assert right["accepted"], right["failures"]


def test_search_expanded_fuses_the_rewrites():
    tools = Tools(UNITS, expander=lambda q: [q, "net profit"])
    hits = tools.search_expanded("how much did it earn", k=5)
    assert hits, "a rewrite should have found the row"


def test_expand_query_parses_the_stub_reply():
    from finrag.agent_rag import expand_query
    client = StubClient(replies=['{"queries": ["net profit", "profit attributable to shareholders"]}'])
    out = expand_query(client, "how much did it earn")
    assert out[0] == "how much did it earn"
    assert "net profit" in out and len(out) == 3


def test_expand_query_survives_a_bad_reply():
    from finrag.agent_rag import expand_query
    client = StubClient(replies=["no json here"])
    assert expand_query(client, "how much did it earn") == ["how much did it earn"]


def test_search_expanded_reranks_when_a_reranker_is_supplied():
    class FakeReranker:
        def predict(self, pairs):
            # rank by the presence of "5,255,815" in the quote
            return [1.0 if "5,255,815" in quote else 0.0 for _q, quote in pairs]

    tools = Tools(UNITS, expander=lambda q: ["profit"], reranker=FakeReranker())
    hits = tools.search_expanded("how much did it earn", k=2)
    assert hits and "5,255,815" in hits[0]["quote"]


def test_claim_helper_picks_the_row_the_question_names():
    from finrag.agent_rag import claim_number

    row = SimpleNamespace(quote="Operating expenses | 26,325 | 26,033",
                          numbers=(26325.0, 26033.0), section="Notes to the FS")
    other = SimpleNamespace(quote="Net fee and commission income | 2,974,059",
                            numbers=(2974059.0,), section="")
    assert claim_number("What were the operating expenses?",
                        [2974059.0, 26325.0], [other, row]) == 26325.0


def test_claim_helper_prefers_the_primary_statement_on_a_tie():
    from finrag.agent_rag import claim_number

    notes = SimpleNamespace(quote="Operating expenses | 26,325",
                            numbers=(26325.0,), section="Notes to the FS")
    primary = SimpleNamespace(quote="Operating expenses | 10,488,740",
                              numbers=(10488740.0,), section="V. ANALYSIS")
    assert claim_number("What were the operating expenses?",
                        [26325.0, 10488740.0], [notes, primary]) == 10488740.0


def test_column_map_validates_shape():
    from finrag.agent_rag import column_map
    m = column_map("2024 | 2023 | Change | Increase (%)",
                   "Net profit | 5,255,815 | 5,080,903 | 174,912 | 3.44")
    assert m == [("2024", 1), ("2023", 2)]


def test_column_map_rejects_messy_tables():
    from finrag.agent_rag import column_map
    # merged header, no years -> unusable
    assert column_map("Operating expenses | 26,325", "Operating expenses | 26,325") is None
    # widths disagree by more than the label offset -> unusable
    assert column_map("2024 | 2023", "a | b | c | d") is None


def test_find_row_matches_labels_only():
    tools = Tools(UNITS)
    hits = tools.find_row("net profit")
    assert hits and hits[0]["quote"].startswith("Net profit")


def test_rounded_millions_satisfy_the_year_column():
    from finrag.agent_rag import verify_answer
    units = {"U:row": SimpleNamespace(
        unit_id="U:row", doc="a.pdf", page=18, channel="table",
        quote="Net profit | 5,255,815 | 5,080,903 | 174,912 | 3.44",
        numbers=(5255815.0, 5080903.0, 174912.0, 3.44))}
    headers = {("a.pdf", 18): "2024 | 2023 | Change | Increase (%)"}
    result = verify_answer("Net profit was RMB5,256 million in 2024, up 3.44%.",
                           ["U:row"], units, headers=headers,
                           question="What was the net profit in 2024?")
    assert result["accepted"], result["failures"]
