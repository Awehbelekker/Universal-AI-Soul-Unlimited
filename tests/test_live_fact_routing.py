"""Live-fact routing + research helpers."""

from core.integrations.wow_tools import (
    claims_supported_by_evidence,
    detect_intent,
    family_topic_relevant,
    needs_live_research,
    research_query_for,
)
from core.routing.task_router import TaskMode, classify_request


def test_world_cup_question_is_live_fact():
    q = "What are your thoughts on the soccer world cup final results?"
    assert needs_live_research(q)
    route = classify_request(q)
    assert route.mode == TaskMode.LIVE_FACT
    assert route.needs_research
    assert not route.use_thinkmesh


def test_who_won_triggers_web_search_intent():
    intent = detect_intent("who won the world cup final?")
    assert intent is not None
    assert intent[0] == "web_search"
    assert "world cup" in intent[1]["query"].lower()


def test_greeting_not_live_fact():
    assert not needs_live_research("Hi")
    assert classify_request("Hi").mode == TaskMode.FAST


def test_family_gate():
    assert family_topic_relevant("remind Sam about lunch")
    assert not family_topic_relevant("world cup final results")


def test_research_query_strips_opinion():
    q = research_query_for(
        "What are your thoughts on the soccer world cup final results?"
    )
    assert "thoughts" not in q.lower()
    assert "2022" in q
    assert "fifa" in q.lower() or "world cup" in q.lower()
    assert "final" in q.lower()


def test_who_won_query_targets_final():
    q = research_query_for("In your opinion who won the last World Cup?")
    assert q == "2022 FIFA World Cup final"

def test_claims_supported_basic():
    evidence = "Argentina won the 2022 FIFA World Cup final 3-3 then on penalties."
    assert claims_supported_by_evidence(
        "Argentina won the 2022 World Cup.", evidence
    )
    assert not claims_supported_by_evidence(
        "Zimbabwe won the 2099 Galactic Cup 99-0.", evidence
    )
