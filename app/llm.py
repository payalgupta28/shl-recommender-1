"""
llm.py
======
One tiny function — `call_llm` — that talks to whichever free-tier provider the
user chose, and hides the per-provider request/response differences behind a
single interface. We ask each provider for JSON output and return the raw text;
parsing happens in agent.py.

Supported providers (all have generous free tiers):
  - groq        : OpenAI-compatible API, very fast Llama models
  - openrouter  : OpenAI-compatible gateway to many free models
  - gemini      : Google Generative Language API (different request shape)
"""
from __future__ import annotations

import httpx

from .config import LLM_TIMEOUT_SECONDS, LLMCredentials, ssl_verify
from .schemas import Message


class LLMError(RuntimeError):
    """Raised when the provider call fails or returns nothing usable."""


def call_llm(creds: LLMCredentials, system_prompt: str, messages: list[Message]) -> str:
    """Send the conversation to the provider and return the model's raw text."""
    if creds.provider in ("groq", "openrouter"):
        return _openai_compatible(creds, system_prompt, messages)
    if creds.provider == "gemini":
        return _gemini(creds, system_prompt, messages)
    raise LLMError(f"Unsupported provider: {creds.provider!r}")


# --------------------------------------------------------------------------- #
# OpenAI-compatible providers (Groq, OpenRouter)
# --------------------------------------------------------------------------- #
_OPENAI_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}


def _openai_compatible(creds, system_prompt, messages) -> str:
    payload = {
        "model": creds.model,
        "messages": [{"role": "system", "content": system_prompt}]
        + [{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
        "temperature": 0.2,            # low -> consistent, grounded answers
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {creds.api_key}"}
    if creds.provider == "openrouter":
        # OpenRouter likes these for free-tier attribution; harmless elsewhere.
        headers["HTTP-Referer"] = "https://shl-recommender.local"
        headers["X-Title"] = "SHL Assessment Recommender"

    data = _post(_OPENAI_ENDPOINTS[creds.provider], payload, headers)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected {creds.provider} response: {data}") from exc


# --------------------------------------------------------------------------- #
# Google Gemini
# --------------------------------------------------------------------------- #
def _gemini(creds, system_prompt, messages) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{creds.model}:generateContent?key={creds.api_key}"
    )
    # Gemini uses "user"/"model" roles and a separate system_instruction field.
    contents = [
        {"role": "model" if m.role == "assistant" else "user",
         "parts": [{"text": m.content}]}
        for m in messages if m.role != "system"
    ]
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    }
    data = _post(url, payload, headers={})
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected gemini response: {data}") from exc


def _post(url: str, payload: dict, headers: dict) -> dict:
    try:
        resp = httpx.post(url, json=payload, headers=headers,
                          timeout=LLM_TIMEOUT_SECONDS, verify=ssl_verify())
    except httpx.HTTPError as exc:
        raise LLMError(f"Network error calling LLM: {exc}") from exc
    if resp.status_code != 200:
        raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()
