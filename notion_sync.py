"""Admin-triggered Notion import from an explicit allowlist.

Designed for single-page cloud function calls. No schedules, broad workspace
enumeration, or source data logged. Requires the caller's RAG write token.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

from cloud_sources import notion_documents
from platform_core import Repository

SUPPORTED = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".docx", ".pdf"}
ID_PATTERN = re.compile(r"^[0-9A-Za-z-]{8,80}$")


def sync_notion_page(repo: Repository, org: str, notion_token: str,
                     configured_ids: list[str], requested_id: str) -> dict:
    """Import one specifically approved Notion page into its knowledge base."""
    if not notion_token or not org or not configured_ids:
        raise ValueError("Notion integration is not configured")
    if not ID_PATTERN.fullmatch(requested_id) or requested_id not in configured_ids:
        raise PermissionError("Notion page not in approved allowlist")
    # Restricted to ONE page per request to bound Vercel execution time.
    result = {"documents_indexed": 0, "documents_unchanged": 0, "chunks_indexed": 0}
    for doc in notion_documents(notion_token, [requested_id], limit=1):
        source = doc.source
        if PurePosixPath(source).suffix.lower() not in SUPPORTED:
            source += "/" + PurePosixPath(doc.filename).name
        digest = hashlib.sha256(doc.data).hexdigest()
        if repo.has_document(org, "default", source, digest):
            result["documents_unchanged"] += 1
        else:
            indexed = repo.ingest(org, "default", source, doc.data)
            result["documents_indexed"] += 1
            result["chunks_indexed"] += indexed["chunks_indexed"]
    return result
