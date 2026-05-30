# 7 · Running, Testing & Deploying

## Prerequisites
- Python 3.10+ (developed on 3.11)
- Internet access for the one-time catalog scrape and for LLM calls

## Run locally (the easy way)

```bash
bash run.sh
# -> http://localhost:8000/
```

`run.sh` creates `.venv`, installs deps, scrapes the catalog if
`data/catalog.json` is missing, and starts Uvicorn.

## Run locally (manual)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/scrape_catalog.py          # one-time; builds the catalog
.venv/bin/python -m uvicorn app.main:app --port 8000
```

## Using an API key

**Option A — in the browser (recommended for demos).** Open the UI, pick a
provider, paste your free key, click *Save*. Stored in `localStorage`, sent as
headers, never persisted on the server.

**Option B — server-side (for SHL's evaluator / CLI eval).** Copy `.env.example`
to `.env` and set:
```
LLM_PROVIDER=groq
LLM_API_KEY=gsk_your_key_here
```
Now `/chat` works without any headers — exactly what SHL's replay harness needs.

Free keys: [Groq](https://console.groq.com/keys) ·
[Gemini](https://aistudio.google.com/apikey) ·
[OpenRouter](https://openrouter.ai/keys)

## Testing

```bash
.venv/bin/python -m pytest          # 12 unit tests (schema + agent behaviour)
.venv/bin/python -m tests.eval      # Recall@10 over tests/traces/*.json
```

- `pytest` uses a **stubbed LLM** → no key, no network needed.
- `tests.eval` uses an LLM **if** `LLM_PROVIDER`/`LLM_API_KEY` are set, else it
  evaluates the offline retrieval fallback.

### Quick manual API checks

```bash
curl localhost:8000/health
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"I need an assessment"}]}'   # clarifies
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"hiring a python data engineer with sql"}]}' # recommends
```

## Refreshing / re-scraping the catalog

```bash
.venv/bin/python scripts/scrape_catalog.py                 # full (with descriptions)
.venv/bin/python scripts/scrape_catalog.py --no-descriptions   # faster, listing only
.venv/bin/python scripts/scrape_catalog.py --max-pages 3       # quick partial test
```

## Deploying to a free host

The service is a standard FastAPI app, so any of these work:

**Render / Railway / Fly:**
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Commit `data/catalog.json` so the host doesn't need to scrape on boot.
- Set env vars `LLM_PROVIDER` and `LLM_API_KEY` in the host dashboard so SHL's
  evaluator (which sends no key) still gets LLM-quality answers.

**Hugging Face Spaces (Docker)** — a minimal `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

### Cold-start note
SHL allows up to 2 minutes for the first `/health` to wake a sleeping free host.
Because the catalog + TF-IDF index build at startup (a second or two for 377
items), the first request after wake is slightly slower; subsequent ones are
fast.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `Catalog not found` on startup | Run `python scripts/scrape_catalog.py` first |
| Replies say "LLM not configured" | No key — add one in the UI or in `.env` |
| `LLM HTTP 401` | Wrong/expired key for the selected provider |
| `LLM HTTP 429` | Free-tier rate limit — wait, or switch provider in the UI |
| `LLM HTTP 404` (model) | Provider renamed the free model — set `X-LLM-Model`/`LLM_MODEL` |
| `LLM HTTP 503` (overloaded) | Free model is busy — retry, or switch provider/model. The agent falls back to retrieval meanwhile. |
| `CERTIFICATE_VERIFY_FAILED` | Corporate TLS-inspecting proxy. We trust the OS store via `truststore` by default; if it persists, set `LLM_CA_BUNDLE=/path/to/corp-ca.pem`, or as a last resort `LLM_VERIFY_SSL=false`. |
| Port already in use | Use another port: `uvicorn ... --port 8001` |

➡️ Next: [Evaluation](08-evaluation.md).
