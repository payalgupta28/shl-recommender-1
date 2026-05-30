"""
schemas.py
==========
The API contract. SHL says: "The schema is non-negotiable. Deviating breaks our
automated evaluator." So we model it strictly with Pydantic, which validates
every request and serialises every response in exactly the required shape.

Request:
    { "messages": [ {"role": "user"|"assistant", "content": "..."} , ... ] }

Response:
    { "reply": "...",
      "recommendations": [ {"name","url","test_type"}, ... ],   # 0..10 items
      "end_of_conversation": false }
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1)


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str  # e.g. "K" or "A, P" — joined letters, per the SHL example


class ChatResponse(BaseModel):
    reply: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    end_of_conversation: bool = False
