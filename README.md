# RAG Demo — local RAG and secure cloud platform foundation

This repository has **two application entrypoints**:

- **Local RAG demo**: `api.py` + `app.py`, using ChromaDB, Sentence Transformers and Ollama.
- **Cloud platform foundation**: `platform_app.py` + `platform_core.py`, using SQLite locally or PostgreSQL on the cloud, with guarded APIs and keyword search. **Not yet a complete semantic RAG production platform.**

## Run the original local RAG application

```bash
git clone https://github.com/s7rosine/rag-demo.git
cd rag-demo
docker compose up --build -d
docker compose exec ollama ollama pull llama3.2:1b
```

Open http://localhost:8501, upload `data/sample.txt` and ask a question. Local API docs: http://localhost:8000/docs.

## Run cloud foundation locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt uvicorn
export RAG_MODE=local RAG_ORG=demo RAG_READ_TOKEN=replace-read RAG_WRITE_TOKEN=replace-write
uvicorn platform_app:app --host 127.0.0.1 --port 8001
```

Use `$env:VARIABLE="value"` syntax in PowerShell instead of `export`. Cloud application API docs: http://localhost:8001/docs.

## Configure Vercel from `.env.example`

Use [`.env.example`](.env.example) as the reference for environment variable names.
In **Vercel → rag-demo → Settings → Environment Variables**, add cloud variables
under **Production**, filling in real values **only in Vercel** (never in GitHub).
The required cloud keys are `RAG_MODE`, `DATABASE_URL`, `RAG_ORG`,
`RAG_READ_TOKEN`, `RAG_WRITE_TOKEN`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, and `TELEGRAM_WEBHOOK_SECRET`.
`TELEGRAM_WEBHOOK_URL` defaults to the verified
`https://rag-demo-gamma.vercel.app/telegram/webhook`; 
`TELEGRAM_KNOWLEDGE_BASE` defaults to `default`.
For generated answers, set `LLM_BASE_URL`, `LLM_MODEL`, and
`LLM_API_KEY` when your provider requires it. `RAG_SQLITE_PATH`,
`CHROMA_PATH`, `OLLAMA_URL`, and `API_URL` are local-demo settings,
not requirements for the Vercel production platform.

After adding or updating cloud values, redeploy the Production deployment,
then check `https://rag-demo-gamma.vercel.app/health`.
A `telegram_webhook` status of `registered` verifies webhook URL registration,
**not** end-to-end Telegram replies or successful database retrieval.
Do not add sensitive/private documents until authorization and retention
controls have been reviewed.

## OpenAI answer generation (provider-switchable)

The first OpenAI provider configuration uses
`LLM_PROVIDER=openai_compatible`,
`LLM_BASE_URL=https://api.openai.com/v1`, and
`LLM_MODEL=gpt-4.1-mini`. Set the separate, private
`LLM_API_KEY` directly in Vercel Production, then redeploy. No API
credentials are committed. This choice does not replace the Anthropic or
Gemini adapters, and does not enable vector embeddings. Full instructions:
[OpenAI model setup](docs/OPENAI_LLM_SETUP.md).

## Approved multi-source RAG architecture

The modular source adapters are in [cloud_sources.py](cloud_sources.py): scoped S3
bucket/prefix, explicitly listed Notion pages, and the direct children of one
Google Drive folder. [sync_knowledge.py](sync_knowledge.py) is a **manual,
opt-in ingestion worker** that checks source content hashes and skips unchanged
documents. The worker needs [requirements-connectors.txt](requirements-connectors.txt)
and explicit cloud credentials. **No background synchronization or deletion
reconciliation is enabled.** S3, Notion, and Drive remain the systems of record.

Provider-independent generation lives in [cloud_models.py](cloud_models.py):
OpenAI-compatible APIs (including compatible OpenRouter/NIM endpoints), native
Anthropic Messages API, and native Gemini API. Select with `LLM_PROVIDER`.
Embedding generation is independently configurable via `EMBEDDING_*`.
Embeddings are not yet persisted; current Vercel retrieval is keyword-only,
so the platform is **not yet semantic vector RAG**.

See [multi-source implementation runbook](docs/MULTISOURCE_RAG.md) before using
real accounts or confidential documents.

## Connect selected Notion pages to the hosted RAG API

The secured `POST /admin/sync/notion` endpoint can import **one explicitly
allowlisted Notion page per call** into the `default` knowledge base.
It requires `RAG_WRITE_TOKEN` and these production settings:
`DATABASE_URL` (persistent Neon PostgreSQL), `RAG_ORG`,
`NOTION_API_TOKEN` (a separately authorized Notion integration token),
and `NOTION_PAGE_IDS` (comma-separated permitted page IDs).
The existing ChatGPT/Composio Notion connection **does not automatically
authorize** your Vercel app. Never copy workspace secrets into GitHub.

Use the secure interactive API documentation at `/docs` to supply the write
token and an approved `page_id`. Ensure only approved non-sensitive pages
are allowed: indexed excerpts may be returned to the authorized Telegram chat.
No automatic syncing, background schedule, deletion tracking, or per-page
source ACL propagation exists yet. See [Notion connection runbook](docs/NOTION_CONNECTION.md).

## Production deployment safeguards

Vercel entrypoint: `platform_app:app` (configured in `pyproject.toml`). **Production requires `RAG_MODE=production`, `DATABASE_URL` for Neon PostgreSQL, `RAG_ORG`, distinct `RAG_READ_TOKEN` and `RAG_WRITE_TOKEN`, and explicit authorization validation.** Vercel's filesystem is ephemeral. The platform must not be used for confidential business data or public writes in its current state.

An OpenAI-compatible LLM provider can be configured through `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`; no secrets belong in Git.

## Development checks

```bash
pip install -r requirements-dev.txt
ruff check src api.py app.py tests platform_core.py platform_app.py
pytest -q
```

## Documentation
- [Platform upgrade status and limitations](docs/PLATFORM_UPGRADE.md)
- [RAG Operations Runbook](docs/RAG_OPERATIONS_RUNBOOK.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

**Known gaps:** see `docs/PLATFORM_UPGRADE.md`. scheduled connector synchronization, OCR, MCP server, pgvector semantic retrieval, n8n orchestration, document deletion reconciliation, memory/business record CRUD, and complete deployment/security verification are not yet implemented.

## Telegram chatbot and RAG retrieval

The cloud module [`rag.py`](rag.py) connects the protected FastAPI service and Telegram webhook to your indexed knowledge base. Telegram commands include `/start`, `/help`, `/search <keywords>`, `/ask <question>`, and natural-language messages. Replies include document source filenames.

**Setup required:** In Vercel, configure `DATABASE_URL` for Neon PostgreSQL, `RAG_ORG`, distinct `RAG_READ_TOKEN` and `RAG_WRITE_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_KNOWLEDGE_BASE`, and the LLM provider settings (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`). Register Telegram's webhook through a secure admin process. This setup is **not complete automatically merely by deploying to Vercel**.

Full setup and troubleshooting: [Telegram + RAG Runbook](docs/TELEGRAM_RAG_RUNBOOK.md). The cloud search implementation is currently keyword-based; pgvector semantic search and webhook deduplication remain future work.
