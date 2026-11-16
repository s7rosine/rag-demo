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

## Telegram database diagnostics (private authorized chat only)

Send `/status` to your Telegram bot. The result checks the actual Neon
connection, confirms whether the `rag_chunks` table is readable, counts
chunks in the configured knowledge base, and reports Notion/model configuration
without exposing passwords, connection strings or provider errors.

- **Database: CONNECTION FAILED**: verify the pooled Neon connection string,
  role/password and TLS in Vercel. Vercel must be redeployed after changes.
- **Index table: MISSING or INACCESSIBLE**: database is reachable but the
  `rag_chunks` schema is not accessible; use an authorized ingest operation
  to initialize the schema after reviewing privileges.
- **Indexed chunks: 0**: connect/ingest an approved Notion page first.
- **Answer model: NOT CONFIGURED**: configure `LLM_PROVIDER`,
  `LLM_MODEL`, `LLM_API_KEY`, and (for compatible providers) `LLM_BASE_URL`.

Do not copy credentials or complete Telegram messages containing confidential
information into issue reports or chats.

## Swagger Authorization fix (November 16, 2026)

The API now publishes an HTTP Bearer security scheme. In
`https://rag-demo-gamma.vercel.app/docs`, select **Authorize** (padlock
button), paste only the `RAG_WRITE_TOKEN` secret in **Value**, then click
**Authorize** and **Close**. Swagger adds the `Bearer ` prefix and the
`Authorization` header automatically for protected routes.

Do NOT type `Bearer ` into the Authorize dialog when it already displays
HTTP Bearer authentication. Do not paste the token into `page_id`, a query
string, or this documentation. The `curl` example shown by Swagger contains
the credential; never publish or screenshot that section once authenticated.
If the old free-text `authorization` header is still shown, perform a hard
refresh or open `/docs` in a fresh browser session after deployment.

Expected outcomes: 401 = no valid bearer header, 403 = incorrect credential or
page not authorized, 503 = Notion/database failure, 200 = successful import.
The Notion account must separately authorize the allowlisted page.

## Safe error classification (November 16, 2026)

The import endpoint returns actionable, sanitized error messages rather than
collapsing every provider/database problem into generic 503:
- **424 Notion token rejected**: verify Vercel `NOTION_API_TOKEN` is a Notion
  internal connection token, not `RAG_WRITE_TOKEN`.
- **424 Page missing/not shared or access denied**: in Notion, add the *same*
  internal connection to the approved page using its Connections menu. Page IDs
  are identifiers, not grants of access.
- **422 No readable text**: the page has no supported Notion text blocks.
- **503 Neon indexing failed**: check DB schema and write privileges.
- **503 Notion rate limited/network error**: resolve provider connectivity.
- **200**: one allowlisted page has been indexed or confirmed unchanged.

Swagger UI (`/docs`) is a developer-facing interface generated from FastAPI
OpenAPI metadata. It allows the RAG admin to inspect routes, authenticate with
a Bearer write token and invoke the protected single-page import. It is not
the employee chatbot, Notion UI, or the knowledge database. It should be
protected from unnecessary public exposure in production, even though actual
import routes require a separate write token.
