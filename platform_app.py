"""Authenticated RAG API for serverless and local use."""
import hmac
import logging
import os

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from platform_core import Repository, Settings, answer

logging.basicConfig(level=logging.WARNING)
# Never enable HTTPX/HTTPCore debug logging; URLs to Telegram contain credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
app = FastAPI(title="RAG Platform", version="0.2.0")
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-platform"}


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
        matches = store.search(org, payload.kb, payload.question, payload.limit)
        response = await answer(payload.question, matches, cfg)
        return {"answer": response, "sources": [
            {"source": m["source"], "document_id": m["document_id"], "chunk_id": m["chunk_id"]}
            for m in matches]}
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
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None =
                           Header(default=None)):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not expected or not x_telegram_bot_api_secret_token or not hmac.compare_digest(
            expected, x_telegram_bot_api_secret_token):
        raise HTTPException(403, "Forbidden")
    update = await request.json()
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not chat_id or not hmac.compare_digest(chat_id, os.getenv("TELEGRAM_CHAT_ID", "")):
        return {"accepted": False}
    text = str(message.get("text") or "")[:2000]
    if not text:
        return {"accepted": True}
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(503, "Telegram integration unavailable")
    if text.split(" ", 1)[0] in ("/start", "/help"):
        response_text = "Send /ask question or /search question. Only configured chats are supported."
    else:
        mode = "search" if text.startswith("/search ") else "ask"
        question = text.partition(" ")[2] if text.startswith(("/ask ", "/search ")) else text
        try:
            matches = store.search(os.getenv("RAG_ORG", ""), "default", question, 4)
            response_text = ("\n".join(m["source"] + ": " + m["text"][:180] for m in matches)
                             if mode == "search" else await answer(question, matches, cfg))
        except Exception:
            response_text = "The knowledge service is currently unavailable."
    # Avoid HTTPX errors exposing a token-bearing URL; suppress chaining.
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            result = await client.post(
                "https://api.telegram.org/bot" + token + "/sendMessage",
                json={"chat_id": chat_id, "text": response_text[:3800]})
            if result.status_code >= 400:
                return {"accepted": False}
    except httpx.HTTPError:
        return {"accepted": False}
    return {"accepted": True}
