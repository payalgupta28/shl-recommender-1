"""
main.py
=======
The FastAPI service. Two API endpoints required by SHL:

    GET  /health  -> {"status": "ok"}        (readiness probe)
    POST /chat    -> stateless conversation -> next reply + optional shortlist

Plus we serve a small web UI at "/" where a user pastes their own free-tier API
key and chats. The key travels in HTTP headers, so the POST /chat body stays
EXACTLY the SHL schema ({"messages": [...]}) and their evaluator is unaffected.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent
from .catalog import Catalog
from .config import resolve_credentials
from .retrieval import Retriever
from .schemas import ChatRequest, ChatResponse

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

# Built once at startup and reused for every request (loading the catalog and
# fitting TF-IDF on each call would be wasteful).
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    catalog = Catalog.load()
    state["catalog"] = catalog
    state["agent"] = Agent(catalog, Retriever(catalog))
    print(f"Loaded catalog with {len(catalog)} assessments.")
    yield
    state.clear()


app = FastAPI(title="SHL Assessment Recommender", version="1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    x_llm_provider: str | None = Header(default=None),
    x_llm_api_key: str | None = Header(default=None),
    x_llm_model: str | None = Header(default=None),
) -> ChatResponse:
    creds = resolve_credentials(x_llm_provider, x_llm_api_key, x_llm_model)
    return state["agent"].respond(body.messages, creds)


# --- Web UI (optional convenience; not part of the SHL API contract) ------- #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/config")
def ui_config() -> dict:
    """Tells the UI how big the catalog is and which providers are supported."""
    from .config import DEFAULT_MODELS, server_llm_ready
    return {"catalog_size": len(state.get("catalog", [])),
            "providers": DEFAULT_MODELS,
            "server_llm_ready": server_llm_ready()}


# Serve CSS/JS assets.
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Never 500 on the conversation path; return a schema-valid, safe reply.
    if request.url.path == "/chat":
        return JSONResponse(status_code=200, content=ChatResponse(
            reply="Sorry, something went wrong on my side. Please rephrase your "
                  "request about SHL assessments.",
            recommendations=[], end_of_conversation=False).model_dump())
    return JSONResponse(status_code=500, content={"detail": str(exc)})
