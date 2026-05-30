"""
agent.py
========
The brain-stem of the system. For one /chat call it:

  1. Builds a search query from the whole conversation and RETRIEVES candidates
     from the catalog (deterministic, offline).
  2. Asks the LLM to choose an ACTION (clarify / recommend / refine / compare /
     refuse) and pick names from those candidates.
  3. GROUNDS the result: every returned name is looked up in the catalog so the
     URL + test type come from real data, never from the model.
  4. Falls back to safe rule-based behaviour if there is no API key or the LLM
     errors out — so a flaky model never takes the whole service down.

Statelessness: everything is derived from the `messages` passed in. We keep no
per-conversation state on the server.
"""
from __future__ import annotations

import json
import re

from .catalog import Catalog
from .config import (MAX_RECOMMENDATIONS, MAX_TURNS, RETRIEVE_K, LLMCredentials)
from .llm import LLMError, call_llm
from .prompts import build_system_prompt
from .retrieval import Retriever
from .schemas import ChatResponse, Message, Recommendation

# Phrases that should be refused without even calling the LLM (cheap guardrail
# against the most obvious prompt-injection / off-topic cases).
_INJECTION_RE = re.compile(
    r"ignore (all |your |previous )?(instructions|rules)|system prompt|"
    r"you are now|pretend to be|reveal your|disregard",
    re.I,
)
_OFFTOPIC_RE = re.compile(
    r"\b(weather|stock|recipe|joke|salary|notice period|legal|lawsuit|"
    r"discrimination law|how do i interview|write code for me)\b",
    re.I,
)


class Agent:
    def __init__(self, catalog: Catalog, retriever: Retriever):
        self.catalog = catalog
        self.retriever = retriever

    # ----- public entry point ------------------------------------------- #
    def respond(self, messages: list[Message], creds: LLMCredentials) -> ChatResponse:
        user_text = " ".join(m.content for m in messages if m.role == "user")
        latest = next((m.content for m in reversed(messages) if m.role == "user"), "")
        candidates = [a for a, _ in self.retriever.search(user_text, RETRIEVE_K)]

        # Near the turn cap we must stop clarifying and commit to a shortlist.
        must_recommend = len(messages) >= MAX_TURNS - 3

        if not creds.is_usable:
            return self._fallback(messages, latest, candidates, must_recommend,
                                   note="(LLM not configured — using offline "
                                        "retrieval. Add an API key for richer replies.)")
        try:
            raw = call_llm(creds, build_system_prompt(candidates, must_recommend), messages)
            return self._from_llm(raw, candidates, must_recommend)
        except (LLMError, ValueError) as exc:
            return self._fallback(messages, latest, candidates, must_recommend,
                                   note=f"(LLM unavailable: {exc}. Showing best matches.)")

    # ----- LLM path ------------------------------------------------------ #
    def _from_llm(self, raw: str, candidates, must_recommend: bool) -> ChatResponse:
        data = _extract_json(raw)
        action = str(data.get("action", "recommend")).lower()
        reply = str(data.get("reply", "")).strip() or "Here is what I found."
        names = data.get("recommendation_names") or []
        end = bool(data.get("end_of_conversation", False))

        # Out of turns but the model still wants to clarify -> force a shortlist.
        # (A genuine refusal stays a refusal; we never recommend on off-topic.)
        if must_recommend and action == "clarify":
            action = "recommend"

        # Ground names against the catalog; silently drop anything not real.
        recs = self._ground(names if isinstance(names, list) else [])

        if action in ("clarify", "refuse"):
            recs = []          # these actions never carry a shortlist
            end = False
        elif action in ("recommend", "refine", "compare"):
            if not recs:       # LLM committed but gave no valid names -> rescue
                recs = self._ground([a.name for a in candidates[:8]])
            end = False          # we never trust the LLM to know when to end a conversation
        return ChatResponse(reply=reply, recommendations=recs[:MAX_RECOMMENDATIONS],
                            end_of_conversation=end)

    # ----- rule-based fallback ------------------------------------------ #
    def _fallback(self, messages, latest, candidates, must_recommend, note) -> ChatResponse:
        if _INJECTION_RE.search(latest) or _OFFTOPIC_RE.search(latest):
            return ChatResponse(
                reply="I can only help with selecting SHL assessments. Tell me "
                      "about the role you're hiring for and what you'd like to "
                      "measure, and I'll suggest assessments.",
                recommendations=[], end_of_conversation=False)

        vague = self._is_vague(latest, candidates)
        if vague and not must_recommend:
            return ChatResponse(
                reply="Happy to help find the right SHL assessments. What role "
                      "are you hiring for, and what would you most like to "
                      "measure (skills, ability, or personality)?",
                recommendations=[], end_of_conversation=False)

        recs = self._ground([a.name for a in candidates[:8]])
        if not recs:
            return ChatResponse(
                reply="I couldn't find matching SHL assessments yet. Could you "
                      "share the role and the key skills involved?",
                recommendations=[], end_of_conversation=False)
        reply = (f"Based on what you've told me, here are {len(recs)} SHL "
                 f"assessments that fit. {note}")
        return ChatResponse(reply=reply, recommendations=recs,
                            end_of_conversation=False)

    # ----- helpers ------------------------------------------------------- #
    def _ground(self, names: list[str]) -> list[Recommendation]:
        out, seen = [], set()
        for name in names:
            item = self.catalog.get(str(name))
            if item and item.url not in seen:
                seen.add(item.url)
                out.append(Recommendation(name=item.name, url=item.url,
                                          test_type=item.test_type_str))
        return out

    # Filler words that carry no information about WHICH assessment fits.
    _FILLER = {
        "i", "we", "need", "want", "looking", "for", "an", "a", "the", "some",
        "assessment", "assessments", "test", "tests", "help", "me", "please",
        "hire", "hiring", "candidate", "candidates", "role", "shl", "recommend",
        "find", "to", "is", "are", "and", "of", "you", "can", "give", "with",
    }

    @classmethod
    def _is_vague(cls, latest: str, candidates) -> bool:
        """Vague = almost no informative words once filler is removed."""
        words = re.findall(r"[a-zA-Z]+", latest.lower())
        informative = [w for w in words if w not in cls._FILLER and len(w) > 2]
        return len(informative) < 2


def _extract_json(raw: str) -> dict:
    """LLMs sometimes wrap JSON in prose/fences. Pull out the first object."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*|```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            return json.loads(match.group(0))
        raise
