# Documentation — read in this order

This folder explains the whole project, from a child-level analogy to a
line-by-line walkthrough. If you read these in order, you'll understand every
file and be able to explain the project to anyone.

| # | Doc | What you'll get |
|---|-----|-----------------|
| 1 | [Explain Like I'm 5](01-explain-like-im-5.md) | The shop-assistant analogy; the whole idea in plain English |
| 2 | [Architecture](02-architecture.md) | The pieces, the diagrams, the two-brain (RAG) design, statelessness |
| 3 | [Request flow](03-request-flow.md) | One `/chat` call traced step-by-step (simple + in-depth for each step) |
| 4 | [Dependencies](04-dependencies.md) | Every library, why it's here, and what we deliberately avoided |
| 5 | [Design decisions](05-design-decisions.md) | Trade-offs, and **what didn't work** + how we measured it |
| 6 | [Tech stack & how to explain it](06-tech-stack-and-how-to-explain.md) | Your presentation cheat-sheet + likely interview Q&A |
| 7 | [Running, testing, deploying](07-running-testing-deploying.md) | Setup, tests, deployment, troubleshooting |
| 8 | [Evaluation](08-evaluation.md) | Recall@10, behaviour probes, how we measured improvement |

## TL;DR for the impatient

- **What:** A conversational agent that recommends real SHL assessments from a
  vague hiring need, via FastAPI `POST /chat` (stateless) + `GET /health`.
- **How:** RAG — a TF-IDF **retriever** finds candidate assessments from a
  scraped 377-item catalog; an **LLM** (your free Groq/Gemini/OpenRouter key)
  decides to clarify / recommend / refine / compare / refuse and picks among the
  candidates; **code grounds** every name back to the catalog so URLs are always
  real.
- **Why it scores:** strict Pydantic schema (hard evals), grounded catalog-only
  URLs (no hallucination), turn-cap enforcement, and safe fallbacks so the
  conversation never breaks.

Start with [doc 1](01-explain-like-im-5.md).
