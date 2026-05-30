# 4 · Dependencies — every library and *why*

We deliberately kept the dependency list **small**. Each one earns its place.
Full list is in [`requirements.txt`](../requirements.txt).

## Runtime dependencies

### `fastapi`
- **What:** A modern Python web framework for building APIs.
- **Why here:** The assignment *requires* a FastAPI service with `/health` and
  `/chat`. FastAPI gives us automatic request validation, auto-generated docs
  (`/docs`), and async support — all with very little code.
- **Why not Flask/Django:** Flask has no built-in validation; Django is far too
  heavy for two endpoints. FastAPI + Pydantic makes the **strict SHL schema**
  self-enforcing.

### `uvicorn[standard]`
- **What:** The ASGI web server that actually runs the FastAPI app.
- **Why here:** FastAPI is just the app definition; something has to listen on a
  port and handle HTTP. Uvicorn is the standard, fast choice. The `[standard]`
  extra pulls in performance bits (uvloop, httptools).

### `pydantic`
- **What:** Data-validation library; models = typed Python classes.
- **Why here:** This is how we make the **"non-negotiable schema"** literally
  impossible to violate. `ChatRequest`/`ChatResponse` define the exact shapes;
  bad input is rejected with HTTP 422 before our code runs, and our output is
  serialised to exactly the required fields. Comes bundled with FastAPI.

### `scikit-learn`
- **What:** Classic machine-learning toolkit. We use `TfidfVectorizer` and
  `cosine_similarity`.
- **Why here:** It powers **retrieval** — turning the user's words into a
  shortlist of catalog items. TF-IDF is:
  - **offline** (no API key, no network) → the service works even before you add
    a key, which keeps it reliable;
  - **fast** (sub-millisecond search over 377 items);
  - **a great fit** for a keyword-heavy catalog ("Java", "Python", "OPQ").
- **Why not a neural embedding model?** For a 377-item, keyword-dominated
  catalog, TF-IDF gives excellent recall with **zero** model download, GPU, or
  latency cost — and it's trivial to explain in an interview. See
  [design decisions](05-design-decisions.md) for the trade-off.

### `numpy`
- **What:** Fast numerical arrays.
- **Why here:** scikit-learn returns NumPy arrays; we use `np.argpartition` to
  grab the top-k similarity scores quickly. It's effectively a transitive
  dependency we use directly for the top-k selection.

### `httpx`
- **What:** A modern HTTP client (like `requests`, but also async + HTTP/2).
- **Why here:** It's how `app/llm.py` calls the LLM providers (Groq, Gemini,
  OpenRouter). We use it with a strict timeout so a slow model can't blow past
  SHL's 30-second cap.
- **Why not the official OpenAI/Google SDKs?** Three providers with three SDKs =
  three heavy dependencies and three different bugs. One thin `httpx` layer over
  their REST APIs is smaller, easier to read, and easy to extend with a new
  provider.

### `python-dotenv`
- **What:** Loads variables from a `.env` file into the environment.
- **Why here:** So you can keep your API key in a local `.env` (for the
  server-side path / SHL's evaluator) without hard-coding secrets. The `.env`
  file is git-ignored.

## Dev / test dependency

### `pytest`
- **What:** The standard Python testing framework.
- **Why here:** Runs the schema/behaviour unit tests in `tests/`. We use it to
  guard the hard evals (schema, catalog-only URLs, 8-turn cap) and the agent
  logic (grounding, anti-hallucination) with a **stubbed LLM**, so tests need no
  key and no network.

## What we are NOT using (and why that's a feature)

| Not used | Why we skipped it |
|----------|-------------------|
| LangChain / LlamaIndex | Adds a large abstraction layer for what is ~200 lines of clear orchestration. We'd rather own and explain the control flow. |
| FAISS / Chroma / pgvector | Vector DBs shine at millions of items; for 377 keyword-heavy items, in-memory TF-IDF is simpler and faster. |
| A database | The service is **stateless** by design — no per-conversation state to store. |
| Sentence-transformer embeddings | Big download + latency for marginal recall gain on this small, keyword-driven catalog. |

The whole runtime footprint is a handful of well-known libraries — easy to
install on a free host and easy to defend in the interview.

➡️ Next: [Design decisions](05-design-decisions.md).
