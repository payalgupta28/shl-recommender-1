"""
test_schema.py
==============
Guards the SHL "hard evals": schema compliance and the structural rules that
their automated evaluator checks on EVERY response. These run with no API key
(offline fallback), so they verify the contract independently of any LLM.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    # Using TestClient as a context manager runs FastAPI's lifespan, which loads
    # the catalog and builds the agent. Without this, state["agent"] is missing.
    with TestClient(app) as c:
        yield c


def post(client, messages):
    return client.post("/chat", json={"messages": messages})


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_chat_response_shape(client):
    r = post(client, [{"role": "user", "content": "Hiring a Java developer, mid level"}])
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"reply", "recommendations", "end_of_conversation"}
    assert isinstance(body["reply"], str) and body["reply"]
    assert isinstance(body["recommendations"], list)
    assert isinstance(body["end_of_conversation"], bool)


def test_recommendation_item_shape_and_bounds(client):
    r = post(client, [{"role": "user", "content": "Need python and sql tests for a data engineer"}])
    recs = r.json()["recommendations"]
    assert 0 <= len(recs) <= 10           # never more than 10
    for item in recs:
        assert set(item) == {"name", "url", "test_type"}
        assert item["url"].startswith("https://www.shl.com/")  # catalog-only URLs


def test_vague_query_does_not_recommend(client):
    recs = post(client, [{"role": "user", "content": "I need an assessment"}]).json()["recommendations"]
    assert recs == []                     # must clarify first, not recommend


def test_off_topic_is_refused_with_no_recs(client):
    body = post(client, [{"role": "user", "content": "What's the weather today?"}]).json()
    assert body["recommendations"] == []


def test_empty_messages_rejected(client):
    assert client.post("/chat", json={"messages": []}).status_code == 422
