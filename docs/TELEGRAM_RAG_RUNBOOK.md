# Telegram + RAG Integration Runbook

## Scope

This repository now includes `rag.py`. It shares document retrieval and grounded generation between FastAPI's `/ask` route and the existing Telegram webhook at `/telegram/webhook`.

**Telegram flow:** Telegram message → authenticated webhook → `rag.py` → selected knowledge base → indexed source excerpts → configured LLM → Telegram answer with source filenames.

Telegram supports `/start`, `/help`, `/search keywords`, `/ask question`, and ordinary messages.

## Required Vercel environment variables

Set these in **Vercel → rag-demo → Settings → Environment Variables**, under the intended environment. Never add real values to GitHub, logs, screenshots or chat:

- `RAG_MODE=production`
- `DATABASE_URL`: Neon PostgreSQL URL. **Required:** without this, production retrieval fails closed.
- `RAG_ORG`: organization identifier, such as your own approved organization slug.
- `RAG_READ_TOKEN`: secret for authenticated REST read endpoints.
- `RAG_WRITE_TOKEN`: a different secret for authenticated document ingestion.
- `TELEGRAM_BOT_TOKEN`: token issued by Telegram BotFather.
- `TELEGRAM_CHAT_ID`: the only permitted Telegram chat ID.
- `TELEGRAM_WEBHOOK_SECRET`: random secret sent in Telegram's `X-Telegram-Bot-Api-Secret-Token` request header.
- `TELEGRAM_KNOWLEDGE_BASE=default`: knowledge base Telegram should search. Use the same knowledge base when indexing documents.
- `LLM_BASE_URL`: OpenAI-compatible provider base endpoint (ending in `/v1`).
- `LLM_MODEL`: model name supported by the provider.
- `LLM_API_KEY`: provider key, if needed.

Telegram can retrieve indexed source excerpts with `/search` even if an LLM is not configured, provided the database is ready.

**Important:** Code does not create or migrate Neon automatically. The configured account requires privileges for the existing schema. Do not store personal or confidential records before verifying access and organizational controls.

## Register Telegram webhook

Telegram must know your public webhook URL, which is:

`https://rag-demo-muku-solutions.vercel.app/telegram/webhook`

The FastAPI cloud application automatically checks Telegram's `getWebhookInfo` during application startup (and when `/health` is requested) and calls `setWebhook` only if the configured URL is missing or different. It sends the saved `TELEGRAM_WEBHOOK_SECRET` as the registration secret. No laptop commands are needed. After deployment, request `GET /health`; the `telegram_webhook` field will report `registered`, `not_configured`, `invalid_url`, or `registration_unavailable`. This status confirms the configured URL, not end-to-end message processing. Avoid sharing bot tokens or webhook secrets. If the secret has changed but the registered URL has not, Telegram cannot reveal the stored secret; rotate the URL or use an authorized re-registration workflow to ensure the new secret takes effect.

## Load documents

1. Configure Neon, `RAG_ORG`, read/write tokens in Vercel.
2. Ingest supported documents using authorized `POST /ingest?kb=default` (the request must contain the form field `file`).
3. Check the ingestion response reports `chunks_indexed` greater than zero.
4. Check retrieval through authorized `POST /search` with `{"question":"test", "kb":"default"}`.
5. Message the Telegram bot with `/search test`, then `/ask a question`.

The cloud retriever currently uses **keyword overlap**, not pgvector semantic search. No scanned-document OCR, automatic Telegram registration or durable webhook deduplication has been implemented.

## Troubleshooting

- **403 at webhook**: the Telegram secret header is absent or incorrect; check registration and Vercel secret configuration.
- **No Telegram reply**: verify the bot token, chat ID, webhook registration, request and function runtime logs. Avoid copying tokens into logs.
- **Knowledge retrieval unavailable**: verify Neon `DATABASE_URL`, `RAG_ORG`, database connection, and that the selected KB contains indexed documents.
- **No matching information**: index files into the exact knowledge base named by `TELEGRAM_KNOWLEDGE_BASE`; check your search terms.
- **Relevant sources but no generated answer**: configure `LLM_BASE_URL`, `LLM_MODEL`, and the required provider key; test `POST /ask` using an authorized client.
- **Duplicate or delayed replies**: Telegram can retry when processing takes too long. This demo has not yet implemented durable update-ID deduplication. Do not use it for transactional actions.
- **500 function error**: inspect Vercel Runtime Logs and ensure dependencies from `pyproject.toml` are installed.

## Verification and security

Run `pytest -q tests/test_rag.py tests/test_telegram_rag.py tests/test_platform_security.py`. Tests mock Telegram and model operations; they do not prove that real Telegram delivery, Neon access, or LLM billing work. Keep the webhook read-only and restrict the allowed chat. Do not expose the ingestion write token to Telegram.

Only declare production chat operational after a genuine authenticated Telegram message successfully returns a cited answer from a persisted Neon document.
