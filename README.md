# SHL Conversational Assessment Recommender

A conversational agent that takes a recruiter from a **vague hiring intent**
("I'm hiring a Java developer") to a **grounded shortlist of real SHL
assessments** — by asking, retrieving, recommending, refining, and comparing,
all while staying strictly inside the SHL catalog.

Built for the SHL Labs "AI Intern" take-home assignment.

---

## What it does (the four behaviours)

| Behaviour | Example user turn | What the agent does |
|-----------|-------------------|---------------------|
| **Clarify** | "I need an assessment" | Asks ONE focused question instead of guessing |
| **Recommend** | "Hiring a mid-level Java dev" | Returns 1–10 real SHL assessments with URLs |
| **Refine** | "Actually, add a personality test" | Updates the shortlist, doesn't start over |
| **Compare** | "OPQ32r vs Verify numerical?" | Explains differences from catalog data only |
| **Refuse** | "What's the weather?" / prompt injection | Politely declines, stays in scope |

Every recommended URL is looked up in the **377-item scraped catalog**, so the
agent can never invent an assessment or a link.

---

## Quick start (2 minutes)

```bash
# 1. From the project folder:
bash run.sh
# (creates .venv, installs deps, scrapes catalog if missing, starts server)

# 2. Open the UI:
#    http://localhost:8000/

# 3. In the UI, pick a provider (Groq / Gemini / OpenRouter), paste a FREE
#    API key, click "Save", and start chatting.
```

Get a free key: [Groq](https://console.groq.com/keys) ·
[Gemini](https://aistudio.google.com/apikey) ·
[OpenRouter](https://openrouter.ai/keys)

> No key yet? The service still runs — it falls back to offline keyword
> retrieval so you can see the plumbing work. Replies get much smarter once a
> key is added.

### Manual run (without run.sh)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/scrape_catalog.py        # builds data/catalog.json
.venv/bin/python -m uvicorn app.main:app --port 8000
```

---

## The API (exactly the SHL contract)

```bash
# Health
curl localhost:8000/health
# -> {"status":"ok"}

# Chat (key is OPTIONAL here; pass it as headers if you want the LLM)
curl -X POST localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'X-LLM-Provider: groq' \
  -H 'X-LLM-Api-Key: YOUR_KEY' \
  -d '{"messages":[{"role":"user","content":"Hiring a mid-level Java developer who works with stakeholders"}]}'
```

Response shape (non-negotiable per the spec):

```json
{
  "reply": "Got it. Here are assessments that fit a mid-level Java dev...",
  "recommendations": [
    {"name": "Java 8 (New)", "url": "https://www.shl.com/...", "test_type": "K"}
  ],
  "end_of_conversation": false
}
```

The `X-LLM-*` headers are **our addition for the web UI**; the request *body* is
exactly `{"messages": [...]}`. The server can also read a key from environment
variables (`.env`) for SHL's evaluator.

---

## Tests & evaluation

```bash
.venv/bin/python -m pytest          # schema + behaviour unit tests (12 tests)
.venv/bin/python -m tests.eval      # Recall@10 over conversation traces
```

---

## Project layout

```
app/            FastAPI service + agent logic
  main.py         endpoints: /health, /chat, web UI
  schemas.py      the strict request/response models
  catalog.py      loads + indexes the scraped catalog
  retrieval.py    TF-IDF search over the catalog
  llm.py          Groq / Gemini / OpenRouter clients
  prompts.py      the system prompt (context engineering)
  agent.py        orchestration: clarify/recommend/refine/compare/refuse
  config.py       settings + per-request credential resolution
data/catalog.json the 377 scraped SHL Individual Test Solutions
scripts/scrape_catalog.py   the scraper
web/            the browser UI (paste-your-key chat)
tests/          unit tests + Recall@10 eval + traces
docs/           full explanation of the project (START HERE to learn it)
```

---

## Learn the whole project

The [`docs/`](docs/) folder explains everything, from a child-level analogy to a
line-by-line request walkthrough:

1. [Explain Like I'm 5](docs/01-explain-like-im-5.md) — analogy + plain English
2. [Architecture](docs/02-architecture.md) — the pieces and how they fit
3. [Request flow](docs/03-request-flow.md) — what happens on one `/chat` call
4. [Dependencies](docs/04-dependencies.md) — every library and *why*
5. [Design decisions](docs/05-design-decisions.md) — trade-offs & what didn't work
6. [Tech stack & how to explain it](docs/06-tech-stack-and-how-to-explain.md)
7. [Running, testing, deploying](docs/07-running-testing-deploying.md)
8. [Evaluation](docs/08-evaluation.md) — Recall@10 and behaviour probes

`APPROACH.md` is the 2-page approach document for the submission.
