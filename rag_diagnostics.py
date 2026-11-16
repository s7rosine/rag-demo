"""Sanitized diagnostics for the single-org RAG platform.

Never echo connection strings, SQL exception bodies, or provider credentials.
This module must only be invoked after authenticated Telegram-chat validation
or an authenticated admin API call.
"""
from __future__ import annotations

import os

from platform_core import Repository, Settings


def rag_status(repository: Repository, settings: Settings, org: str, kb: str) -> str:
    """Check real storage connectivity and indexed records without writing data."""
    messages = ["RAG diagnostics"]
    if not org:
        return "RAG diagnostics\nOrganization: NOT CONFIGURED (RAG_ORG)"
    if settings.mode == "production" and not settings.database_url:
        return "RAG diagnostics\nDatabase: NOT CONFIGURED (DATABASE_URL)"
    if not settings.database_url:
        return "RAG diagnostics\nDatabase: local mode; not Neon"
    url = settings.database_url.strip()
    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        return "RAG diagnostics\nDatabase: invalid URL format (expected postgresql://...)"
    conn = None
    try:
        conn, placeholder, _ = repository.connect()
        row = conn.execute("SELECT 1").fetchone()
        if not row or row[0] != 1:
            return "RAG diagnostics\nDatabase: connection validation failed"
    except Exception:
        return ("RAG diagnostics\nDatabase: CONNECTION FAILED. "
                "Check Neon hostname, role/password, SSL, and pooled connection URL.")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    messages.append("Database: CONNECTED")
    conn = None
    try:
        conn, placeholder, _ = repository.connect()
        count = conn.execute(
            f"SELECT COUNT(*) FROM rag_chunks WHERE org={placeholder} AND kb={placeholder}",
            (org, kb),
        ).fetchone()[0]
        messages.append("Indexed chunks (" + kb + "): " + str(count))
    except Exception as exc:
        # Only SQLSTATE is inspected: never include driver error text,
        # connection details, SQL statements, or document content in replies.
        sqlstate = getattr(exc, "sqlstate", None)
        if sqlstate == "42P01":
            messages.append("Index table: NOT CREATED (rag_chunks)")
        elif sqlstate == "42501":
            messages.append("Index table: PERMISSION DENIED (rag_chunks)")
        elif sqlstate == "3F000":
            messages.append("Index schema: NOT FOUND")
        else:
            messages.append("Index table: MISSING or INACCESSIBLE (rag_chunks)")
        count = None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    notion_ready = bool(os.getenv("NOTION_API_TOKEN")) and bool(os.getenv("NOTION_PAGE_IDS"))
    messages.append("Notion credentials/allowlist: " + ("CONFIGURED" if notion_ready else "INCOMPLETE"))
    provider = os.getenv("LLM_PROVIDER", "openai_compatible")
    model_ready = bool(os.getenv("LLM_MODEL")) and (
        provider in ("anthropic", "gemini") or bool(os.getenv("LLM_BASE_URL"))
    )
    messages.append("Answer model: " + ("CONFIGURED (not tested)" if model_ready else "NOT CONFIGURED"))
    if count == 0:
        messages.append("Next: Import an approved Notion page before /search.")
    elif count is None:
        messages.append("Next: Initialize and check the RAG database schema.")
    else:
        messages.append("Next: Try /search <keywords from an indexed document>.")
    return "\n".join(messages)
