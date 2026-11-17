# Configure OpenAI as the first LLM — Cloud RAG

Updated: 2026-11-16

## Goal and current state

The Notion → Neon → Telegram `/search` path was verified with 17 indexed
chunks. This is keyword retrieval, not embeddings-based semantic search.

OpenAI is the first **answer-generation** provider. The modular
`cloud_models.py` still supports `openai_compatible`, `anthropic`,
and `gemini` without changing document ingestion or the storage backend.
`EMBEDDING_*` settings are independent. No semantic vector index has
been deployed.

## Vercel Production settings

In Vercel → rag-demo → Settings → Environment Variables:

| Key | Value | Classification |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai_compatible` | Plain |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Plain |
| `LLM_MODEL` | `gpt-4.1-mini` | Plain |
| `LLM_API_KEY` | Your OpenAI API project key | Sensitive, secret |

Do not commit an API key to GitHub, Notion or screenshots. Create a project
API key from https://platform.openai.com/api-keys and store it directly
in Vercel. A ChatGPT subscription is separate from OpenAI API billing.
Check https://platform.openai.com/settings/organization/billing for
the relevant API organization/project billing status and usage limits.

After storing/updating `LLM_API_KEY`, redeploy Production. `/status` in
the authorized Telegram chat will show the model setting and whether an
API key is present; it does NOT make a billable live test request.

To verify generation, message the Telegram bot:

```text
/ask What is the purpose of the RAG project?
```

Expected behavior: retrieval finds relevant chunks, then a configured model
generates an answer grounded in the retrieved context. Do not claim success
until a live response is verified, preferably with useful citations.

Use `/search RAG` to test retrieval alone, without invoking an LLM.
The app's `/ask` endpoint also supports authenticated REST clients, but
needs a separate `RAG_READ_TOKEN`, which is not needed for the allowed
Telegram chat.

## Switching providers (keep configuration separate)

- OpenAI and OpenAI-compatible: `LLM_PROVIDER=openai_compatible`, and
  set the approved `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`.
- Anthropic: `LLM_PROVIDER=anthropic`, set a supported Claude model and
  Anthropic API key; use the native endpoint and avoid retaining an
  OpenAI-specific `LLM_BASE_URL` (remove it to use the native default).
- Gemini: `LLM_PROVIDER=gemini`, set an available Gemini model and API
  key; remove the OpenAI base URL to use the native default.

Always change these keys together and redeploy. Model switching is still
subject to separate provider authentication, credits, usage limits, and
real-world verification. The HTTP contract and RAG indexing are not tied
to OpenAI.

## Privacy and reliability

Once LLM generation is enabled, some retrieved Notion text is transmitted
to the configured AI provider to answer a question. Use only approved,
non-confidential documents until data-handling and access-control reviews
are complete. The current demo does not implement complete enterprise ACL
propagation, scheduled ingestion, vector search, or token-cost controls.
