# Multi-source RAG: S3 + Notion + Google Drive

Updated: 2026-11-15

## Implementation boundaries

- `cloud_sources.py`: read-only, scoped source adapters, 8 MB maximum per document.
- `sync_knowledge.py`: **explicit** `--apply` flag; otherwise configuration-only preview. It skips unchanged documents already indexed for the same organization, KB, and source.
- `cloud_models.py`: OpenAI-compatible, Anthropic, Gemini generation adapters, plus independent OpenAI-compatible embedding interface.
- Vercel API is unchanged; existing Telegram webhook and authentication remain intact.
- S3, Notion, and Drive are **original sources**. Neon stores indexed chunks, not the originals.
- **Not yet implemented:** scheduled incremental polling, source deletion propagation, pgvector schema and retrieval, full provider-agnostic embeddings, cross-tenant ACL propagation, rate-limit retries, and Drive nested folder crawl.

## Configure an authorized sync worker

Install dependencies in the worker (not required in the FastAPI serverless image):

```bash
python -m pip install -r requirements-connectors.txt
```

Set `RAG_MODE=production`, `DATABASE_URL`, and `RAG_ORG` securely.
Use `.env.example` for the complete list of placeholders and required source
settings. Do not save real secrets in Git, logs, screenshots, or Notion.

Source choices:

- **S3** — `S3_BUCKET`, `S3_PREFIX`, and `AWS_REGION`. The worker uses
  the AWS credential chain; prefer an IAM role with `s3:ListBucket` restricted
  to the configured prefix and `s3:GetObject` only for that prefix.
- **Notion** — `NOTION_API_TOKEN` and `NOTION_PAGE_IDS` (comma-separated
  exact page IDs). Share only those pages with the Notion integration.
  Reads blocks recursively to a bounded nesting depth; rich-text content only.
- **Google Drive** — `GDRIVE_FOLDER_ID` and `GDRIVE_SERVICE_ACCOUNT_JSON`
  (a private JSON credential supplied through the worker's secret manager).
  Share only the desired folder with the service account. Imports direct-child
  files with supported extensions plus native Google Docs (text export). It
  does not ingest native Sheets, Slides, or nested folder contents.

Review scope first:

```bash
python sync_knowledge.py --source s3 --kb default
python sync_knowledge.py --source notion --kb default
python sync_knowledge.py --source gdrive --kb default
```

Start explicit ingestion **only** after approved permissions and database schema:

```bash
python sync_knowledge.py --source s3 --kb default --limit 50 --apply
python sync_knowledge.py --source notion --kb default --limit 30 --apply
python sync_knowledge.py --source gdrive --kb default --limit 50 --apply
```

These commands run from a trusted worker or ephemeral cloud job with credentials,
not from a Telegram webhook request or automatically during Vercel startup.
**Do not run --apply on private or workplace documents without authorization.**

## Model configuration

Set `LLM_PROVIDER=openai_compatible`, `anthropic`, or `gemini`.
Set `LLM_MODEL` and `LLM_API_KEY`; for the OpenAI-compatible option,
set `LLM_BASE_URL` (e.g. the authorized provider's HTTPS `/v1` URL).
Native Anthropic/Gemini endpoints are defaults if no URL is supplied.

Embedding configuration is **separate**:
`EMBEDDING_PROVIDER=openai_compatible`, `EMBEDDING_BASE_URL`,
`EMBEDDING_MODEL`, `EMBEDDING_API_KEY`. Vector generation APIs are
available to the future indexing pipeline, but **vectors are not yet stored
or searched**.

## Before production

1. Create/verify Neon schema and enforce per-organization document authorization.
2. Plan pgvector migrations, dimension/model versioning, and hybrid retrieval.
3. Add cloud worker scheduling, durable sync cursors/checkpoints, retries,
   deletion reconciliation, and permission-change invalidation.
4. Test each external connector with approved synthetic fixtures and real
   least-privilege credentials in a nonproduction environment.
5. Test model-provider switching and source-cited answers with actual indexed
   documents before declaring the entire system production-ready.
