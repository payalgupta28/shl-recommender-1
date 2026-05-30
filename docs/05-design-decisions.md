# 5 · Design Decisions, Trade-offs & What Didn't Work

This is the "defend it in the interview" document. Each decision states the
**choice**, the **why**, and the **trade-off**.

## 1. Retrieval (TF-IDF) is separate from reasoning (LLM)

- **Choice:** A deterministic TF-IDF retriever produces ~30 candidates; the LLM
  only *chooses among* and *describes* them.
- **Why:** It cleanly splits "find real things" (must be honest) from "talk
  nicely" (the LLM's strength). It directly satisfies two hard requirements:
  catalog-only URLs and grounded comparisons.
- **Trade-off:** If the retriever misses a relevant item entirely, the LLM can't
  recover it (it never saw it). We mitigate with `k=30` (generous recall) and
  title-weighted, type-expanded documents.

## 2. Grounding happens in code, not in the prompt

- **Choice:** Every name the LLM returns is re-looked-up in `catalog.py`;
  anything not found is dropped, and URLs/types come from the catalog object.
- **Why:** Prompts *ask* for good behaviour; code *guarantees* it. Even a
  hallucinating model cannot produce a fake URL through our system.
- **Trade-off:** If the LLM slightly misspells a real name, the exact-ish
  (normalised) match may drop it. We normalise aggressively (lowercase,
  strip punctuation) to reduce this, and rescue with retrieval candidates.

## 3. Stateless, with read-only state built once

- **Choice:** No DB, no sessions. Catalog + TF-IDF index built at startup only.
- **Why:** Matches the spec, scales horizontally, and is crash-safe.
- **Trade-off:** Re-sending full history each call costs a few tokens; for an
  8-turn cap this is negligible.

## 4. The API key is a per-request header (UI), with env fallback (evaluator)

- **Choice:** `X-LLM-Provider` / `X-LLM-Api-Key` / `X-LLM-Model` headers; body
  stays exactly `{"messages":[...]}`.
- **Why:** Lets a user bring their own free-tier key in the browser **without**
  breaking the SHL request schema, while the deployed instance can still serve
  the evaluator from a server-side `.env`.
- **Trade-off:** Two credential paths to reason about; handled in one small
  function (`resolve_credentials`) with headers taking priority.

## 5. Multi-provider via one thin httpx layer

- **Choice:** Support Groq, Gemini, OpenRouter through ~80 lines in `llm.py`.
- **Why:** Free tiers have rate limits and outages; letting the user switch
  provider keeps the demo alive. No heavy SDKs.
- **Trade-off:** We maintain the request/response shapes ourselves. They're
  stable, well-documented REST APIs, so this is low-risk and easy to extend.

## 6. The agent never crashes the conversation

- **Choice:** Malformed JSON, LLM errors, or a missing key all fall back to safe
  rule-based behaviour; a global handler returns a schema-valid 200 on `/chat`.
- **Why:** "A non-deterministic conversation should not make the system fall
  apart" (the spec). Robustness protects the hard-eval and behaviour-probe
  scores even when the model misbehaves.
- **Trade-off:** Fallback replies are less fluent than the LLM's. Acceptable —
  correctness and schema-compliance beat eloquence.

## 7. Turn-cap awareness is enforced, not just requested

- **Choice:** Near the cap, `must_recommend` forces a shortlist even if the LLM
  wants to keep clarifying (genuine refusals still refuse).
- **Why:** SHL caps conversations at 8 messages; an agent stuck clarifying would
  score 0 recall on that trace.
- **Trade-off:** Occasionally we commit slightly early; better than never
  committing.

---

## What didn't work (and how we measured it)

### ❌ Query expansion that appended test-type keywords to the query
- **What we tried:** When the query mentioned "developer", we appended words
  like *knowledge skills technical programming coding simulation* to the query
  before TF-IDF.
- **What happened:** It **diluted sharp keywords**. The query "java developer
  backend" started returning *Count Out The Money*, *Typing*, and *Accounts
  Payable Simulation* instead of the Java tests, because the generic appended
  words matched dozens of items and drowned out the rare, decisive word "java".
- **How we measured:** A quick retrieval probe printing the top-5 for "java
  developer backend" before/after. Before the fix: 0 Java items in top-5. After
  removing expansion: top-4 were *Java 8*, *Java Frameworks*, *Java Design
  Patterns*, *Informatica (Developer)*.
- **Fix:** Drop query expansion. Instead, bake the type words into each
  **document** (`search_document`) once. Now "personality" still matches P-type
  items, but a specific term like "java" stays decisive.

### ❌ A too-loose "vague query" rule
- **What we tried:** Mark a query vague only if it had < 4 words.
- **What happened:** "I need an assessment" is exactly 4 words, so it slipped
  through and the offline path **recommended on turn 1** — which a behaviour
  probe explicitly penalises.
- **How we measured:** The `test_vague_query_does_not_recommend` unit test
  failed.
- **Fix:** Strip filler words ("need", "assessment", "hire", ...) and call it
  vague when < 2 *informative* words remain. The test passes and "I need an
  assessment" now correctly clarifies.

### ❌ Relying on the LLM to honour the turn cap by instruction alone
- **What we tried:** Just tell the model "you're almost out of turns, recommend
  now."
- **What happened:** A stubbed model that ignored the instruction kept
  returning `clarify`, leaving empty recommendations at the cap.
- **How we measured:** The `test_turn_cap_forces_recommendation` unit test.
- **Fix:** Enforce in code — `must_recommend` converts a `clarify` into a
  `recommend` (rescued with retrieved candidates).

### ❌ Scraping with a generic `<tr data-course-id>` row matcher
- **What we tried:** Parse catalog rows by the `data-course-id` attribute.
- **What happened:** **Zero** Individual-Test rows parsed — only the
  *Pre-packaged* table rows carry `data-course-id`; the Individual rows don't.
- **How we measured:** Printed marker offsets and row counts; all 12
  `data-course-id` hits were in the pre-packaged table.
- **Fix:** Isolate the "Individual Test Solutions" table slice first, then match
  any `<tr>` containing a product link. Result: 377 items scraped cleanly.

➡️ Next: [Tech stack & how to explain it](06-tech-stack-and-how-to-explain.md).
