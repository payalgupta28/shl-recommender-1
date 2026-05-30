"""
eval.py — offline Recall@10 harness
====================================
Replays conversation traces against the agent IN-PROCESS and reports
Recall@10, the headline metric SHL grades on.

    Recall@10 = (relevant items found in top 10) / (total relevant items)

Each trace file in tests/traces/*.json looks like:
    {
      "name": "java_developer",
      "persona": "Recruiter hiring a mid-level Java developer ...",
      "user_turns": ["first user message", "answer to clarifying Q", ...],
      "expected": ["Java 8 (New)", "Core Java (Advanced Level) (New)", ...]
    }

The replay feeds user_turns one at a time, lets the agent reply, and keeps the
LAST non-empty recommendation list as the final shortlist (mirroring how the
real user ends the chat once a shortlist appears). Respects the 8-message cap.

Run:
    .venv/bin/python -m tests.eval
It uses an LLM if LLM_PROVIDER + LLM_API_KEY are set in the environment;
otherwise it evaluates the offline retrieval fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.agent import Agent
from app.catalog import Catalog, normalize
from app.config import MAX_TURNS, resolve_credentials
from app.retrieval import Retriever
from app.schemas import Message

TRACES_DIR = Path(__file__).resolve().parent / "traces"


def recall_at_k(predicted: list[str], expected: list[str], k: int = 10) -> float:
    if not expected:
        return 1.0
    top = {normalize(n) for n in predicted[:k]}
    hit = sum(1 for e in expected if normalize(e) in top)
    return hit / len(expected)


def replay(agent: Agent, creds, trace: dict) -> list[str]:
    """Run one trace and return the final recommended names."""
    messages: list[Message] = []
    final: list[str] = []
    for turn in trace["user_turns"]:
        if len(messages) >= MAX_TURNS:        # honour the turn cap
            break
        messages.append(Message(role="user", content=turn))
        resp = agent.respond(messages, creds)
        messages.append(Message(role="assistant", content=resp.reply))
        if resp.recommendations:
            final = [r.name for r in resp.recommendations]
    return final


def main() -> None:
    cat = Catalog.load()
    agent = Agent(cat, Retriever(cat))
    creds = resolve_credentials(os.getenv("LLM_PROVIDER"), os.getenv("LLM_API_KEY"),
                                os.getenv("LLM_MODEL"))
    mode = f"LLM={creds.provider}/{creds.model}" if creds.is_usable else "offline-fallback"
    print(f"Evaluating in {mode} mode\n" + "-" * 56)

    traces = sorted(TRACES_DIR.glob("*.json"))
    if not traces:
        print("No traces found. Add SHL's traces to tests/traces/.")
        return

    scores = []
    for path in traces:
        trace = json.loads(path.read_text())
        predicted = replay(agent, creds, trace)
        score = recall_at_k(predicted, trace["expected"], 10)
        scores.append(score)
        found = [e for e in trace["expected"]
                 if normalize(e) in {normalize(p) for p in predicted[:10]}]
        print(f"{trace['name']:<22} Recall@10 = {score:.2f}  "
              f"({len(found)}/{len(trace['expected'])} relevant found)")

    print("-" * 56)
    print(f"Mean Recall@10 over {len(scores)} traces = {sum(scores)/len(scores):.3f}")


if __name__ == "__main__":
    main()
