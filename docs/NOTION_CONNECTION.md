# Notion knowledge base → Vercel RAG connection

Updated 2026-11-15. Cloud setup only; no laptop terminal is necessary.

## Connection architecture

Notion (source) → authenticated scoped Notion API → Vercel FastAPI
`POST /admin/sync/notion` → Neon PostgreSQL `rag_chunks` →
protected RAG `/search` and `/ask` → authorized Telegram bot.

The Notion connector works only for explicitly allowlisted page IDs.
One page is imported per administrative request. It reads Notion blocks,
including supported nested rich text, up to the documented depth/size limit.

## Prerequisites in Vercel Production

- `RAG_MODE=production`
- `DATABASE_URL`: Neon PostgreSQL connection URL (secret)
- `RAG_ORG`: non-secret single-organization scope
- `RAG_WRITE_TOKEN`: long, strong independent secret that authorizes ingestion
- `RAG_READ_TOKEN`: different independent secret for REST search and Q&A
- `NOTION_API_TOKEN`: read-only integration token from your Notion configuration;
  do not reuse or extract ChatGPT/Composio OAuth credentials
- `NOTION_PAGE_IDS`: comma-separated specific approved page IDs
- `TELEGRAM_KNOWLEDGE_BASE=default` (must match imported KB)

No `NOTION_API_TOKEN`, `NOTION_PAGE_IDS`, or `DATABASE_URL` were configured
when the project was inspected on November 15, 2026. A ChatGPT Notion
connection alone cannot provide Vercel access.

## Complete the cloud setup

1. In Notion, create/configure a read-only Notion integration using the Notion
   developer settings. Share **only approved, non-sensitive pages** with that
   integration using the Notion page's connection settings.
2. In Vercel → rag-demo → Settings → Environment Variables, add the token as
   sensitive, the page ID allowlist, Neon connection, and independent RAG tokens.
   The token must never be pasted into AI chats or GitHub.
3. Redeploy Production so that FastAPI receives the new environment settings.
4. Open `https://rag-demo-gamma.vercel.app/docs` and authorize with
   `RAG_WRITE_TOKEN`, then invoke `POST /admin/sync/notion` with a single
   allowlisted `page_id` in the JSON body. A request with no token returns
   401; an unapproved page returns 403; an incomplete setup returns 503.
5. Check that the result contains `documents_indexed: 1` and positive
   `chunks_indexed` (or `documents_unchanged: 1` on a repeated run).
6. Test authenticated `POST /search` for a phrase in the imported page
   using `kb: default`, then ask the Telegram bot `/search phrase`.

The `/docs` endpoint may be suitable for an initial administrator test; a
scheduled service account job should be used later for production sync.
Do not connect employer, patient, family, or personal confidential pages to
this single-chat prototype without a reviewed authorization boundary.

## Known limitations

- No paginated workspace-wide crawl, database-row traversal, or rich media OCR.
- No recurring schedule, source delete propagation, permission-change detection,
  webhook deduplication, or provider rate-limit retry policy.
- The cloud retriever remains keyword-based; pgvector semantic indexing is pending.
- The Notion integration token is separate from your connected ChatGPT
  Notion account and must be explicitly provisioned for Vercel.
