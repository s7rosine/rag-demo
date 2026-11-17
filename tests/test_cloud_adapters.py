"""No-network tests for cloud source adapters and provider selection."""
import asyncio
import sys
from types import SimpleNamespace

import pytest

import cloud_models
import cloud_sources
from platform_core import Repository, Settings


def test_s3_adapter_respects_scope_and_file_filter(monkeypatch):
    calls = []

    class Body:
        def read(self, limit):
            return b"valid document"

        def close(self):
            pass

    class Paginator:
        def paginate(self, **kwargs):
            calls.append(kwargs)
            return [{"Contents": [
                {"Key": "docs/a.txt", "Size": 14},
                {"Key": "docs/skip.exe", "Size": 10},
                {"Key": "docs/huge.pdf", "Size": 9_000_000},
            ]}]

    class Client:
        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return Paginator()

        def get_object(self, **kwargs):
            assert kwargs["Bucket"] == "approved"
            assert kwargs["Key"] == "docs/a.txt"
            return {"Body": Body()}

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *a, **k: Client()))
    results = list(cloud_sources.s3_documents("approved", "docs/", limit=2))
    assert [r.source for r in results] == ["s3://approved/docs/a.txt"]
    assert calls[0]["Prefix"] == "docs/"


def test_notion_adapter_uses_explicit_page_ids(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [{
                    "id": "block1", "type": "paragraph", "has_children": False,
                    "paragraph": {"rich_text": [{"plain_text": "A useful note"}]},
                }],
                "has_more": False,
            }

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["headers"]["Notion-Version"] == "2022-06-28"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, params):
            calls.append(url)
            return Response()

    monkeypatch.setattr(cloud_sources.httpx, "Client", Client)
    documents = list(cloud_sources.notion_documents("test-token", ["page-123"]))
    assert documents[0].source == "notion://page-123"
    assert documents[0].filename.endswith(".md")
    assert documents[0].data == b"A useful note"
    assert len(calls) == 1


def test_neon_sync_fails_closed_without_database(tmp_path):
    repo = Repository(Settings(mode="production", database_url="",
                               sqlite_path=str(tmp_path / "db.sqlite3")))
    with pytest.raises(RuntimeError):
        repo.initialize()


def test_unchanged_source_detection(tmp_path):
    repo = Repository(Settings(mode="local", database_url="",
                               sqlite_path=str(tmp_path / "db.sqlite3")))
    result = repo.ingest("org", "default", "s3://demo/doc.txt", b"Source content.")
    assert repo.has_document("org", "default", "s3://demo/doc.txt", result["document_id"])
    assert not repo.has_document("other", "default", "s3://demo/doc.txt", result["document_id"])


def test_no_implicit_source_access(monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(ValueError):
        cloud_sources.configured_documents("s3")
    with pytest.raises(ValueError):
        cloud_sources.configured_documents("notion")
    with pytest.raises(ValueError):
        cloud_sources.configured_documents("invalid")


def test_generate_native_providers(monkeypatch):
    calls = []

    class Response:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            pass

        def json(self):
            if "anthropic" in self.url:
                return {"content": [{"type": "text", "text": "Claude answer"}]}
            if "generativelanguage" in self.url:
                return {"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]}
            return {"choices": [{"message": {"content": "Compatible answer"}}]}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append(url)
            return Response(url)

    monkeypatch.setattr(cloud_models.httpx, "AsyncClient", Client)
    async def invoke(provider):
        return await cloud_models.generate("system", "question", provider=provider,
                                           model="model-x", base_url=None, api_key="fake")
    assert asyncio.run(invoke("anthropic")) == "Claude answer"
    assert asyncio.run(invoke("gemini")) == "Gemini answer"
    assert len(calls) == 2


def test_embedding_provider_can_differ_from_llm(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"index": 1, "embedding": [3.0, 4.0]},
                             {"index": 0, "embedding": [1.0, 2.0]}]}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            assert url.endswith("/embeddings")
            return Response()

    monkeypatch.setattr(cloud_models.httpx, "AsyncClient", Client)
    vectors = asyncio.run(cloud_models.embed_texts(
        ["first", "second"], model="embedding-model", base_url="https://example.org/v1",
    ))
    assert vectors == [[1.0, 2.0], [3.0, 4.0]]


def test_openai_compatible_chat_request_and_portability(monkeypatch):
    """Verify OpenAI endpoint, payload, bearer key and alternative base URL."""
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "Grounded test answer"}}]}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    monkeypatch.setattr(cloud_models.httpx, "AsyncClient", Client)
    async def run(url):
        return await cloud_models.generate(
            "Use provided knowledge only", "What is RAG?",
            provider="openai_compatible", model="gpt-4.1-mini",
            base_url=url, api_key="fake-test-key",
        )
    assert asyncio.run(run("https://api.openai.com/v1")) == "Grounded test answer"
    assert calls[0][0] == "https://api.openai.com/v1/chat/completions"
    assert calls[0][1]["headers"] == {"Authorization": "Bearer fake-test-key"}
    assert calls[0][1]["json"]["model"] == "gpt-4.1-mini"
    assert asyncio.run(run("https://other-provider.example/v1")) == "Grounded test answer"
    assert calls[1][0] == "https://other-provider.example/v1/chat/completions"


def test_openai_quota_error_sanitized(monkeypatch):
    import httpx

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            req = httpx.Request("POST", url)
            response = httpx.Response(429, json={
                "error": {"code": "insufficient_quota", "message": "PRIVATE"}
            }, request=req)
            response.raise_for_status()

    monkeypatch.setattr(cloud_models.httpx, "AsyncClient", Client)
    with pytest.raises(cloud_models.ModelProviderError) as error:
        asyncio.run(cloud_models.generate("system", "question",
                                         provider="openai_compatible",
                                         model="gpt-4.1-mini",
                                         base_url="https://api.openai.com/v1",
                                         api_key="test-secret"))
    assert error.value.reason == "quota_exhausted"
    assert "PRIVATE" not in str(error.value)
    assert "test-secret" not in str(error.value)
