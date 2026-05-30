"""
test_agent.py
=============
Tests the agent's logic with a STUBBED LLM, so we verify our orchestration
(grounding, action handling, turn cap, anti-hallucination) without needing a
real API key or network.
"""
import json

import pytest

from app import agent as agent_module
from app.agent import Agent
from app.catalog import Catalog
from app.config import LLMCredentials
from app.retrieval import Retriever
from app.schemas import Message

FAKE_CREDS = LLMCredentials(provider="groq", api_key="test", model="m")


@pytest.fixture(scope="module")
def ag():
    cat = Catalog.load()
    return Agent(cat, Retriever(cat))


def stub_llm(monkeypatch, payload: dict):
    monkeypatch.setattr(agent_module, "call_llm",
                        lambda *a, **k: json.dumps(payload))


def test_real_names_are_grounded_with_catalog_urls(ag, monkeypatch):
    stub_llm(monkeypatch, {
        "action": "recommend",
        "reply": "Here are some fits.",
        "recommendation_names": ["Java 8 (New)", "Python (New)"],
        "end_of_conversation": True,
    })
    resp = ag.respond([Message(role="user", content="java and python dev")], FAKE_CREDS)
    names = [r.name for r in resp.recommendations]
    assert "Java 8 (New)" in names and "Python (New)" in names
    for r in resp.recommendations:
        assert r.url.startswith("https://www.shl.com/")


def test_hallucinated_names_are_dropped(ag, monkeypatch):
    # "Totally Fake Test 9000" is not in the catalog -> must be silently removed,
    # but we must still rescue with real candidates rather than return nothing.
    stub_llm(monkeypatch, {
        "action": "recommend",
        "reply": "x",
        "recommendation_names": ["Totally Fake Test 9000", "Java 8 (New)"],
        "end_of_conversation": False,
    })
    resp = ag.respond([Message(role="user", content="java developer")], FAKE_CREDS)
    names = [r.name for r in resp.recommendations]
    assert "Totally Fake Test 9000" not in names
    assert "Java 8 (New)" in names


def test_clarify_action_clears_recommendations(ag, monkeypatch):
    stub_llm(monkeypatch, {
        "action": "clarify",
        "reply": "What seniority?",
        "recommendation_names": ["Java 8 (New)"],  # should be ignored
        "end_of_conversation": False,
    })
    resp = ag.respond([Message(role="user", content="hiring")], FAKE_CREDS)
    assert resp.recommendations == []
    assert resp.end_of_conversation is False


def test_recommend_clamped_to_ten(ag, monkeypatch):
    many = [f"Name {i}" for i in range(20)]
    stub_llm(monkeypatch, {"action": "recommend", "reply": "x",
                           "recommendation_names": many, "end_of_conversation": False})
    resp = ag.respond([Message(role="user", content="java developer")], FAKE_CREDS)
    assert len(resp.recommendations) <= 10


def test_malformed_json_falls_back_safely(ag, monkeypatch):
    monkeypatch.setattr(agent_module, "call_llm", lambda *a, **k: "not json at all")
    resp = ag.respond([Message(role="user", content="java developer mid level")], FAKE_CREDS)
    # Falls back to retrieval-based recommendation; still schema-valid.
    assert isinstance(resp.recommendations, list)
    assert all(r.url.startswith("https://www.shl.com/") for r in resp.recommendations)


def test_turn_cap_forces_recommendation(ag, monkeypatch):
    # Even if the model wants to keep clarifying, near the cap we must commit.
    stub_llm(monkeypatch, {"action": "clarify", "reply": "another question?",
                           "recommendation_names": [], "end_of_conversation": False})
    long_history = []
    for i in range(6):
        long_history.append(Message(role="user", content="java developer"))
        long_history.append(Message(role="assistant", content="ok"))
    resp = ag.respond(long_history, FAKE_CREDS)
    # must_recommend is true, so even though the stub clarifies we override to
    # recommend and rescue with real candidates.
    assert len(resp.recommendations) > 0
    assert all(r.url.startswith("https://www.shl.com/") for r in resp.recommendations)
