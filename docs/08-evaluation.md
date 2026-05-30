# 8 · Evaluation — how we know it's good

SHL scores three things. Here's how the project targets each, and how you can
measure it yourself.

## 1. Hard evals (must pass)

These are pass/fail structural checks on every response.

| Hard eval | How we guarantee it | Where it's tested |
|-----------|---------------------|-------------------|
| Schema compliance on every response | Pydantic `ChatResponse`; global handler returns schema-valid 200 even on errors | `test_schema.py` |
| Only catalog items in `recommendations` | `_ground()` re-looks-up every name in the catalog; drops unknowns | `test_agent.py::test_hallucinated_names_are_dropped` |
| 1–10 items when committing | Clamp to 10; rescue to ≥1 when committing | `test_agent.py::test_recommend_clamped_to_ten` |
| Turn cap (≤8) honoured | `must_recommend` forces a shortlist near the cap | `test_agent.py::test_turn_cap_forces_recommendation` |

Run them: `.venv/bin/python -m pytest`

## 2. Recall@10 on final recommendations

> Recall@10 = (relevant items found in top 10) / (total relevant items),
> averaged over conversation traces.

We provide an **offline replay harness**: `tests/eval.py`. It replays each trace
in `tests/traces/*.json`, takes the final shortlist, and computes Recall@10.

```bash
.venv/bin/python -m tests.eval
```

Example run (offline fallback, our 3 sample traces):
```
data_engineer          Recall@10 = 1.00  (3/3 relevant found)
java_developer         Recall@10 = 0.75  (3/4 relevant found)
numerical_reasoning    Recall@10 = 1.00  (3/3 relevant found)
Mean Recall@10 over 3 traces = 0.917
```

With an LLM key set (`LLM_PROVIDER`/`LLM_API_KEY`), recall typically improves
because the LLM picks subtler matches (e.g. mapping "works with stakeholders" to
a personality/work-style assessment) that pure keyword search ranks lower.

### Using SHL's official traces
Drop SHL's provided trace files into `tests/traces/` using the same shape:
```json
{ "name": "...", "persona": "...",
  "user_turns": ["...", "..."],
  "expected": ["Exact Catalog Name", "..."] }
```
Then re-run `python -m tests.eval`. (If SHL's traces use a different field
layout, adapt the small `replay()`/loader in `tests/eval.py` — it's ~15 lines.)

### Why our `expected` names are real
Every expected name in the sample traces is a verified entry in
`data/catalog.json` (e.g. *Java 8 (New)*, *Python (New)*, *Occupational
Personality Questionnaire OPQ32r*, *SHL Verify Interactive – Numerical
Reasoning*), so Recall@10 is meaningful and not measuring against phantom items.

## 3. Behaviour probes (binary assertions)

Each probe is a tiny conversation with a yes/no assertion. Our coverage:

| Probe | Behaviour | Guarded by |
|-------|-----------|------------|
| Refuses off-topic | "What's the weather?" → no recs, polite decline | `test_off_topic_is_refused_with_no_recs` + system prompt |
| No recommend on turn 1 for vague | "I need an assessment" → clarify, empty recs | `test_vague_query_does_not_recommend` |
| Honours edits | "add a personality test" → updates shortlist | `REFINE` policy in `prompts.py` |
| No hallucinations | fake names dropped; URLs catalog-only | `_ground()` + `test_hallucinated_names_are_dropped` |
| Prompt-injection resistant | "ignore your instructions" → refuse | `_INJECTION_RE` fallback + system prompt rule |

## How we measured *improvements* during development

We treated retrieval quality as the leading indicator and used fast probes:

1. **Retrieval probes** — printed the top-5 catalog hits for fixed queries
   ("java developer backend", "numerical reasoning", "personality"). This is how
   we caught the query-expansion dilution bug (Java items vanished from the
   top-5) and confirmed the fix (top-4 became Java tests).
2. **Vague-detection probe** — the `test_vague_query_does_not_recommend` test
   turned a subjective rule into a pass/fail signal.
3. **Recall@10 harness** — the headline number, run after each change to make
   sure a fix didn't regress overall recall.

See [design decisions](05-design-decisions.md) for the specific before/after
results of each fix.

## Honest limitations
- Sample traces are illustrative; the real signal comes from SHL's full
  public + holdout traces.
- The offline fallback is intentionally simpler than the LLM path; the deployed
  service should always run with a key for best Recall@10 and behaviour scores.
- TF-IDF can miss purely semantic matches with no shared keywords; `k=30` and a
  capable LLM mitigate this, and embeddings are the natural next upgrade.
