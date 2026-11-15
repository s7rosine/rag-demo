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

**Known gaps:** see `docs/PLATFORM_UPGRADE.md`. Notion/Drive connectors, OCR, MCP server, pgvector semantic retrieval, n8n workflow orchestration, automatic Telegram webhook registration, memory/business record CRUD, and complete deployment/security verification have not yet been implemented.
