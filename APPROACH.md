# Approach Document — Conversational SHL Assessment Recommender

*(Submission companion. Target: ≤2 pages. Full detail lives in `docs/`.)*

## 1. Design overview

The agent is a **Retrieval-Augmented Generation (RAG)** system with three
clearly separated responsibilities, served by a **stateless FastAPI** app:

1. **Retriever (deterministic, offline)** — a TF-IDF index over the scraped
   catalog returns ~30 candidate assessments for the user's cumulative query.
2. **LLM reasoner** — decides the conversational *action* (clarify / recommend /
   refine / compare / refuse) and selects which candidates actually fit.
3. **Grounding (code)** — every assessment name the LLM returns is re-looked-up
   in the catalog; unknown names are dropped and the real URL + test type are
   attached. **URLs are never taken from the model's text.**

This split is the heart of the design: the retriever is *honest and fast*, the
LLM is *smart and conversational*, and code-level grounding makes
"catalog-only, no hallucinated URLs" a **guarantee**, not a hope.

The API is stateless — each `POST /chat` carries the full history; the only
server state is the read-only catalog + TF-IDF index built once at startup.

## 2. Catalog / retrieval setup

- **Scraper** (`scripts/scrape_catalog.py`) paginates the SHL catalog's
  *Individual Test Solutions* table (`?type=1&start=N`), parsing name, view URL,
  test-type letters, and remote/adaptive flags, then enriches each item with its
  description page. Result: **377 assessments** → `data/catalog.json`. (Scraping
  is one-time; the live service only reads the JSON.)
- **Retrieval** uses scikit-learn `TfidfVectorizer` (1–2 grams, English
  stop-words, sublinear TF) + cosine similarity. Each catalog *document* is the
  title (double-weighted) + job levels + description + **human-readable
  test-type words** (so "personality" matches P-type items without diluting
  sharp terms like "java"). Chosen over embeddings because the catalog is small
  and keyword-heavy — TF-IDF gives strong recall with zero model/latency cost
  and is easy to defend.

## 3. Prompt design (context engineering)

The system prompt (`app/prompts.py`) supplies three things every turn:
(a) a **behaviour policy** defining each action and the hard scope rules (refuse
off-topic / legal / general hiring advice / prompt-injection; never invent
items); (b) a **strict JSON output contract**
(`action`, `reply`, `recommendation_names`, `end_of_conversation`); and (c) the
**candidate list** — the only assessments the LLM may name. Temperature is low
(0.2) for consistency. Near the 8-message cap, a `must_recommend` instruction is
added *and enforced in code*.

LLM access (`app/llm.py`) is one thin `httpx` layer over three free-tier
providers (Groq, Gemini, OpenRouter), each asked for JSON output, with a ~24s
timeout to stay under SHL's 30s cap. The web UI lets a user paste their own key,
sent as `X-LLM-*` headers so the `/chat` **body stays exactly** `{"messages":[]}`;
the server can alternatively read a key from `.env` for SHL's evaluator.

## 4. Robustness (so the conversation never falls apart)

- Tolerant JSON extraction (handles fenced/prose-wrapped output).
- If the LLM errors or no key is present, a **rule-based fallback** clarifies /
  recommends / refuses safely.
- A global handler returns a **schema-valid 200** on `/chat` even on unexpected
  errors.
- Turn-cap enforcement converts a late `clarify` into a `recommend` (rescued
  with retrieved candidates).

## 5. Evaluation approach

- **Unit tests** (`pytest`, stubbed LLM — no key/network) guard the hard evals:
  schema shape, catalog-only URLs, ≤10 items, turn cap, vague→clarify,
  off-topic→refuse, hallucinated-name dropping.
- **Recall@10 harness** (`tests/eval.py`) replays conversation traces and
  reports mean Recall@10. On three illustrative traces it scores **0.917 even in
  offline (no-LLM) mode**; SHL's official traces can be dropped into
  `tests/traces/` and re-run.
- **Retrieval probes** were the leading indicator during development.

### What didn't work (and how we measured it)
- **Query expansion** (appending type keywords to the query) **diluted sharp
  terms** — "java developer" returned *Typing*/*Accounts Payable* instead of
  Java tests. Measured via a top-5 retrieval probe; fixed by moving type words
  into the *documents* instead of the query (top-4 became Java tests).
- A **<4-word vague rule** let "I need an assessment" recommend on turn 1;
  caught by a unit test; fixed with filler-word stripping (<2 informative words).
- **Trusting the prompt alone** for the turn cap left empty recs at the cap;
  caught by a unit test; fixed by enforcing `must_recommend` in code.
- A `data-course-id` **row scraper matched 0 individual tests** (only
  pre-packaged rows have that attribute); fixed by isolating the Individual table
  and matching any product-link row → 377 items.

## 6. AI-tool usage

An AI coding assistant was used to scaffold boilerplate and draft documentation.
All architecture and engineering decisions — the retriever/LLM split, code-level
grounding, the header-based key design, the scraper fixes, and the
retrieval-dilution debugging — are mine and are documented in `docs/`.

## 7. Stack
Python 3.11 · FastAPI · Uvicorn · Pydantic · scikit-learn (TF-IDF) · NumPy ·
httpx (Groq/Gemini/OpenRouter) · python-dotenv · vanilla JS UI · pytest.
