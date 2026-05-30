# 6 · Tech Stack & How to Explain This Project to Someone Else

This doc is your **presentation cheat-sheet**. Use it when explaining the
project in an interview, a demo, or to a teammate.

## The tech stack in one table

| Layer | Technology | One-line reason |
|-------|-----------|-----------------|
| Language | **Python 3.11** | Standard for AI/ML + web glue |
| API framework | **FastAPI** | Required; auto-validates the strict schema |
| Web server | **Uvicorn** | Runs the FastAPI app over HTTP |
| Validation | **Pydantic** | Makes the SHL schema impossible to break |
| Retrieval | **scikit-learn TF-IDF + cosine similarity** | Fast, offline, honest catalog search |
| Math | **NumPy** | Top-k selection over similarity scores |
| LLM access | **httpx** → Groq / Gemini / OpenRouter | One thin layer over 3 free-tier providers |
| Config/secrets | **python-dotenv** | Keep API keys out of the code |
| Frontend | **Vanilla HTML/CSS/JS** | No build step; paste-your-key chat UI |
| Testing | **pytest** | Schema + behaviour tests with a stubbed LLM |
| Data source | **Custom scraper** (stdlib `urllib` + regex) | Builds `data/catalog.json` from shl.com |

**Architecture pattern:** Retrieval-Augmented Generation (RAG) with a
**deterministic retriever + an LLM reasoner + code-level grounding**, served by
a **stateless** API.

## The 60-second pitch (say this first)

> "It's a conversational recommender for SHL's assessment catalog. A recruiter
> describes a role in plain language, and the agent clarifies if it's vague,
> then recommends real SHL assessments, refines as the recruiter changes their
> mind, and compares assessments on request — never going outside the catalog.
>
> Under the hood it's RAG: a TF-IDF retriever finds candidate assessments from
> the 377 I scraped, and an LLM decides what to do and which candidates fit. The
> key trick is that the LLM can only *pick from* what the retriever found, and I
> re-look-up every name in the catalog in code — so it can never invent a fake
> test or URL. The API is stateless and FastAPI + Pydantic enforce SHL's exact
> response schema."

## The 5 talking points to always mention

1. **The four behaviours + refusal.** Clarify, Recommend, Refine, Compare, and
   staying in scope (refuse off-topic / prompt injection). Map each to the demo.

2. **Two-brain design (RAG).** Deterministic retriever (honest, fast, offline)
   vs. LLM reasoner (smart, conversational). Explain *why* you split them.

3. **Grounding / anti-hallucination in code.** "Every URL comes from the
   catalog" is guaranteed by `_ground()`, not by trusting the prompt. This is
   the single most important point for SHL's hard evals.

4. **Statelessness.** Full history per request, no server memory → scalable,
   crash-safe, matches the spec.

5. **Robustness & the 8-turn cap.** Bad JSON, LLM outages, or no key all fall
   back safely; near the cap we force a shortlist. "A non-deterministic
   conversation doesn't make the system fall apart."

## Anticipated interview questions (and crisp answers)

- **"Why TF-IDF and not embeddings?"** → 377 keyword-heavy items; TF-IDF gives
  excellent recall with zero model download/latency and is trivial to explain.
  I'd switch to embeddings if the catalog grew large or queries got more
  semantic. (See [dependencies](04-dependencies.md).)

- **"How do you stop hallucinated assessments/URLs?"** → The LLM returns *names
  only*, chosen from a candidate list I gave it. I then look every name up in
  the catalog and attach the real URL/type; unknown names are dropped. URLs are
  never taken from the model's text.

- **"How is the API key handled in the UI without breaking the schema?"** → It
  travels as HTTP headers (`X-LLM-*`); the `/chat` *body* stays exactly
  `{"messages":[...]}`. Headers override the server's env key.

- **"What if the LLM returns garbage or times out?"** → `_extract_json` is
  tolerant; on failure the agent uses a rule-based fallback, and `/chat` always
  returns a schema-valid 200.

- **"How did you handle the turn cap?"** → Counted messages; near the cap,
  `must_recommend` forces a shortlist in code, not just in the prompt.

- **"How did you build the catalog?"** → A scraper paginates the Individual Test
  Solutions table, parses name/URL/test-type/remote/adaptive, and enriches each
  with its description page. 377 items → `data/catalog.json`.

- **"Where could it fail / what would you improve?"** → If the retriever misses
  an item the LLM can't recover it (mitigated by k=30); I'd add hybrid
  TF-IDF+embeddings and an LLM-judge eval loop with more traces.

## How to run the demo live (script)

1. `bash run.sh` → open `http://localhost:8000/`.
2. Paste a free Groq key, click Save.
3. Type **"I need an assessment"** → it **clarifies** (no recommendations).
4. Type **"Hiring a mid-level Java developer who works with stakeholders"** →
   it **recommends** Java + work-style assessments with real links.
5. Type **"Also add a personality test"** → it **refines** (keeps Java, adds
   OPQ).
6. Type **"What's the difference between OPQ32r and Verify numerical reasoning?"**
   → it **compares** using catalog descriptions.
7. Type **"What's the weather today?"** → it **refuses** politely.

That sequence demonstrates all five behaviours in under two minutes.

## What to say if you used AI tools to build it

Be honest and specific (SHL asks for this): e.g. "I used an AI coding assistant
to scaffold boilerplate and draft docs, but I designed the architecture, made
the retrieval/grounding decisions, debugged the scraper and retrieval-dilution
issue myself, and can explain every file." Owning the design is what they score.

➡️ Next: [Running, testing, deploying](07-running-testing-deploying.md).
