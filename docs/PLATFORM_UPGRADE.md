# RAG Platform upgrade — implementation status

## Existing functions retained
The original `api.py`, `app.py`, and `src/rag/*` remain untouched for local ChromaDB/Ollama and Streamlit use. `platform_app.py` adds a separate FastAPI serverless entrypoint with additional guarded routes. This is an additive initial upgrade, **not a completed production migration**.

## Cloud API
`platform_app:app` serves `/health`, `/knowledge-bases`, `/search`, `/ask`, `/query`, `/ingest`, and `/telegram/webhook`.

Define `RAG_MODE=production`, `DATABASE_URL` (Neon PostgreSQL connection string), `RAG_ORG`, `RAG_READ_TOKEN`, and `RAG_WRITE_TOKEN` in Vercel encrypted environment variables. Writes fail closed without production storage. Never use local SQLite for durable Vercel writes. Local development defaults to SQLite.

`LLM_BASE_URL` is an OpenAI-compatible URL root ending with `/v1`; `LLM_MODEL` and `LLM_API_KEY` configure generation. This can support OpenAI-compatible, OpenRouter and NIM endpoints with their supported models. The v2 search currently uses **keyword overlap, not semantic vector retrieval**; embeddings and pgvector migration remain pending.

## Telegram
Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `TELEGRAM_WEBHOOK_SECRET`. Configure Telegram webhook independently using an approved secure setup process. **Automatic registration, delivery retries, and event deduplication are not yet implemented.** Only the specified chat ID is accepted. Do not enable real bots until endpoint and duplicate-delivery testing is complete.

## Not implemented yet
MCP protocol server, pgvector embeddings, OCR, image extraction, connector ingestion, n8n workflows, business records, memory semantics, event idempotency, full rate limiting, enterprise multi-tenant authorization, credential rotation automation, automatic webhook registration, and complete deployment regression testing. Avoid claiming these exist.

## Security
Never disclose tokens or query parameters in logs. Read and write tokens are separate, using constant-time comparisons. Authorization is checked before database access; default is deny. Only `RAG_ORG` is scoped; this is a **single-org application**, not yet multi-tenant. API errors do not include third-party exception strings.

## Local validation
```bash
pip install -r requirements-vercel.txt
RAG_MODE=local RAG_ORG=demo RAG_READ_TOKEN=read-test RAG_WRITE_TOKEN=write-test uvicorn platform_app:app --port 8001
```
Windows PowerShell users should set environment variables through `$env:NAME = "value"`. The cloud deployment is not considered production-ready until persistent storage, webhook and MCP protocol tests pass.
