"""Admin-triggered Notion import from an explicit allowlist.

Designed for single-page cloud function calls. No schedules, broad workspace
enumeration, or source data logged. Requires the caller's RAG write token.
"""
from __future__ import annotations

import hashlib
import re

import httpx
from pathlib import PurePosixPath

from cloud_sources import notion_documents
from platform_core import Repository

SUPPORTED = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".docx", ".pdf"}
ID_PATTERN = re.compile(r"^[0-9A-Za-z-]{8,80}$")


class NotionImportError(Exception):
    """Safe internal classification; never carries raw provider messages."""

    def __init__(self, stage: str, kind: str):
        self.stage = stage
        self.kind = kind
        super().__init__(stage + ":" + kind)


def _notion_failure(exc: Exception) -> NotionImportError:
    """Map upstream failures without returning URLs, headers or response bodies."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return NotionImportError("notion", "token_rejected")
        if status == 403:
            return NotionImportError("notion", "access_denied")
        if status == 404:
            return NotionImportError("notion", "page_not_shared_or_missing")
        if status == 429:
            return NotionImportError("notion", "rate_limited")
        return NotionImportError("notion", "upstream_error")
    if isinstance(exc, httpx.RequestError):
        return NotionImportError("notion", "network_error")
    if isinstance(exc, ValueError):
        return NotionImportError("notion", "invalid_or_unreadable_content")
    return NotionImportError("notion", "unexpected_error")


def sync_notion_page(repo: Repository, org: str, notion_token: str,
                     configured_ids: list[str], requested_id: str) -> dict:
    """Import one specifically approved Notion page into its knowledge base."""
    if not notion_token or not org or not configured_ids:
        raise ValueError("Notion integration is not configured")
    if not ID_PATTERN.fullmatch(requested_id) or requested_id not in configured_ids:
        raise PermissionError("Notion page not in approved allowlist")
    # Enumerate one page before opening a DB transaction, so we can
    # distinguish Notion API failures from database indexing failures.
    try:
        docs = list(notion_documents(notion_token, [requested_id], limit=1))
    except Exception as exc:
        raise _notion_failure(exc) from None

    if not docs:
        raise NotionImportError("notion", "no_readable_text")

    result = {"documents_indexed": 0, "documents_unchanged": 0, "chunks_indexed": 0}
    for doc in docs:
        source = doc.source
        if PurePosixPath(source).suffix.lower() not in SUPPORTED:
            source += "/" + PurePosixPath(doc.filename).name
        digest = hashlib.sha256(doc.data).hexdigest()
        try:
            if repo.has_document(org, "default", source, digest):
                result["documents_unchanged"] += 1
            else:
                indexed = repo.ingest(org, "default", source, doc.data)
                result["documents_indexed"] += 1
                result["chunks_indexed"] += indexed["chunks_indexed"]
        except ValueError:
            raise NotionImportError("index", "unsupported_document") from None
        except Exception:
            raise NotionImportError("database", "index_write_failed") from None
    return result
