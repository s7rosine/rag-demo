"""Notion cloud ingestion: privacy, allowlist and unchanged document tests."""
import hashlib

from fastapi.testclient import TestClient

import notion_sync
import platform_app
from cloud_sources import SourceDocument


def test_non_allowlisted_page_refused(monkeypatch):
    repo = object()
    try:
        notion_sync.sync_notion_page(repo, "org", "token", ["approved-123"], "other-123")
        assert False, "should reject"
    except PermissionError:
        pass


def test_import_and_deduplicate(monkeypatch):
    class Store:
        def __init__(self):
            self.docs = set()
            self.calls = []

        def has_document(self, org, kb, source, digest):
            return (org, kb, source, digest) in self.docs

        def ingest(self, org, kb, source, data):
            self.calls.append((org, kb, source, data))
            self.docs.add((org, kb, source, hashlib.sha256(data).hexdigest()))
            return {"chunks_indexed": 2}

    store = Store()
    monkeypatch.setattr(
        notion_sync, "notion_documents",
        lambda token, ids, limit: iter([SourceDocument("notion://approved-123", "approved-123.md", b"Safe test data")]),
    )
    first = notion_sync.sync_notion_page(store, "org", "test-token", ["approved-123"], "approved-123")
    second = notion_sync.sync_notion_page(store, "org", "test-token", ["approved-123"], "approved-123")
    assert first == {"documents_indexed": 1, "documents_unchanged": 0, "chunks_indexed": 2}
    assert second["documents_unchanged"] == 1
    assert len(store.calls) == 1
    assert store.calls[0][2] == "notion://approved-123/approved-123.md"


def test_endpoint_requires_admin_token(monkeypatch):
    monkeypatch.delenv("RAG_WRITE_TOKEN", raising=False)
    response = TestClient(platform_app.app).post(
        "/admin/sync/notion", json={"page_id": "approved-123"}
    )
    assert response.status_code == 401


def test_endpoint_refuses_unconfigured_database(monkeypatch):
    monkeypatch.setenv("RAG_WRITE_TOKEN", "test-write")
    monkeypatch.setenv("RAG_ORG", "test-org")
    monkeypatch.setenv("NOTION_API_TOKEN", "test-provider-token")
    monkeypatch.setenv("NOTION_PAGE_IDS", "approved-123")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = TestClient(platform_app.app).post(
        "/admin/sync/notion",
        headers={"Authorization": "Bearer test-write"},
        json={"page_id": "approved-123"},
    )
    assert response.status_code == 503
    assert "test-provider-token" not in response.text


def test_endpoint_denies_unknown_page(monkeypatch):
    monkeypatch.setenv("RAG_WRITE_TOKEN", "test-write")
    monkeypatch.setenv("RAG_ORG", "test-org")
    monkeypatch.setenv("NOTION_API_TOKEN", "test-provider-token")
    monkeypatch.setenv("NOTION_PAGE_IDS", "approved-123")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    response = TestClient(platform_app.app).post(
        "/admin/sync/notion",
        headers={"Authorization": "Bearer test-write"},
        json={"page_id": "notallowed-123"},
    )
    assert response.status_code == 403
