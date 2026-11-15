"""Authenticated RAG API for serverless and local use."""
import hmac
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from platform_core import Repository, Settings
from rag import ask_knowledge, search_knowledge, telegram_answer, telegram_search
from telegram_registration import ensure_webhook, webhook_status

logging.basicConfig(level=logging.WARNING)
# Never enable HTTPX/HTTPCore debug logging; URLs to Telegram contain credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # In Vercel, each new serverless instance can initialize independently.
    # Registration is conditional on the Telegram webhook URL being different.
    await ensure_webhook()
    yield


app = FastAPI(title="RAG Platform", version="0.2.1", lifespan=lifespan)
cfg = Settings()
store = Repository(cfg)


def authorize(authorization: str | None = Header(default=None), scope: str = "read"):
    expected = os.getenv("RAG_READ_TOKEN" if scope == "read" else "RAG_WRITE_TOKEN", "")
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    if not hmac.compare_digest(authorization[7:], expected):
        raise HTTPException(403, "Forbidden")
    org = os.getenv("RAG_ORG", "")
    if not org:
        raise HTTPException(503, "Organization is not configured")
    return org


def read_access(authorization: str | None = Header(default=None)):
    return authorize(authorization, "read")


def write_access(authorization: str | None = Header(default=None)):
    return authorize(authorization, "write")


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    kb: str = Field(default="default", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    limit: int = Field(default=5, ge=1, le=20)


@app.get("/")
async def home():
    await ensure_webhook()
    return {
        "service": "RAG Platform",
        "status": "online",
        "documentation": "/docs",
        "health": "/health",
        "message": "This is a REST API. Persistent knowledge features require protected database configuration.",
    }


@app.get("/health")
async def health():
    # Fallback if the serverless runtime does not execute lifespan callbacks.
    await ensure_webhook()
    return {"status": "ok", "service": "rag-platform",
            "telegram_webhook": webhook_status()}


@app.get("/knowledge-bases")
def knowledge_bases(org: str = Depends(read_access)):
    try:
        return {"knowledge_bases": store.list_kbs(org)}
    except Exception:
        raise HTTPException(503, "Storage unavailable") from None


@app.post("/search")
def search(payload: Query, org: str = Depends(read_access)):
    try:
        return {"matches": store.search(org, payload.kb, payload.question, payload.limit)}
    except Exception:
        raise HTTPException(503, "Search unavailable") from None


@app.post("/ask")
async def ask(payload: Query, org: str = Depends(read_access)):
    try:
        result = await ask_knowledge(
            payload.question, org, kb=payload.kb, limit=payload.limit,
            repository=store, settings=cfg,
        )
        return result
    except Exception:
        raise HTTPException(503, "Question answering unavailable") from None


@app.post("/ingest")
async def ingest(file: UploadFile = File(...), kb: str = "default",
                 org: str = Depends(write_access)):
    if not kb or len(kb) > 64 or not kb.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(422, "Invalid knowledge base")
    data = await file.read(8_000_001)
    if len(data) > 8_000_000:
        raise HTTPException(413, "File too large")
    try:
        return store.ingest(org, kb, file.filename or "unknown", data)
    except ValueError:
        raise HTTPException(400, "Invalid document or unsupported format") from None
    except Exception:
        raise HTTPException(503, "Ingestion unavailable") from None


@app.post("/query")
async def legacy_query(payload: Query, org: str = Depends(read_access)):
    return await ask(payload, org)


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Read-only webhook; validate Telegram header and allowed chat before retrieval."""
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not secret or not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        secret, x_telegram_bot_api_secret_token
    ):
        raise HTTPException(403, "Forbidden")

    # Telegram's real webhook update payload always contains a message object.
    try:
        update = await request.json()
    except ValueError:
        raise HTTPException(400, "Invalid update") from None
    message = update.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    allowed = os.getenv("TELEGRAM_CHAT_ID", "")
    if not allowed or not chat_id or not hmac.compare_digest(chat_id, allowed):
        return {"accepted": False}

    text = str(message.get("text") or "").strip()[:2000]
    if not text:
        return {"accepted": True}

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(503, "Telegram integration unavailable")

    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@", 1)[0].lower()
    org = os.getenv("RAG_ORG", "")
    kb = os.getenv("TELEGRAM_KNOWLEDGE_BASE", "default")
    if cmd in ("/start", "/help"):
        reply = "Ask a question or use /ask <question> or /search <keywords>. Answers use indexed documents."
    elif cmd in ("/ask", "/search") and not arg.strip():
        reply = "Please include a question after " + cmd + "."
    else:
        question = arg.strip() if cmd in ("/ask", "/search") else text
        try:
            if cmd == "/search":
                results = search_knowledge(question, org, kb=kb, repository=store, settings=cfg)
                reply = telegram_search(results)
            else:
                result = await ask_knowledge(question, org, kb=kb, repository=store, settings=cfg)
                reply = telegram_answer(result)
        except Exception:
            # Never send database URLs, credentials or exception messages to users.
            reply = "Knowledge retrieval is currently unavailable. Check database and model configuration."

    # No token-bearing URLs may be logged. Keep HTTPX/HTTPCore below DEBUG.
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            response = await client.post(
                "https://api.telegram.org/bot" + token + "/sendMessage",
                json={"chat_id": chat_id, "text": reply[:3800]},
            )
        return {"accepted": response.status_code == 200}
    except httpx.HTTPError:
        return {"accepted": False}
