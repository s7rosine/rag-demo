"""Contract tests for RAG integration; no paid API or live Telegram needed."""
import asyncio

import pytest

from rag import ask_knowledge, search_knowledge, telegram_answer, telegram_search
from platform_core import Settings


class FakeRepository:
    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    def search(self, org, kb, query, limit):
        self.calls.append((org, kb, query, limit))
        return self.matches[:limit]


def test_ask_with_citations(monkeypatch):
    matches = [
        {"source": "runbook.md", "document_id": "abc", "chunk_id": "1", "text": "The answer is RAG."},
        {"source": "runbook.md", "document_id": "abc", "chunk_id": "2", "text": "RAG retrieves relevant text."},
    ]
    store = FakeRepository(matches)

    async def fake_answer(question, retrieved, settings):
        assert question == "What is RAG?"
        assert len(retrieved) == 2
        return "RAG retrieves documents (runbook.md)."

    monkeypatch.setattr("rag.answer", fake_answer)
    result = asyncio.run(ask_knowledge(
        "What is RAG?", "demo-org", repository=store, settings=Settings(),
    ))
    assert result["sources"] == [{"source": "runbook.md", "document_id": "abc"}]
    assert store.calls == [("demo-org", "default", "What is RAG?", 4)]
    assert "Sources: runbook.md" in telegram_answer(result)


def test_no_match_no_hallucination():
    result = asyncio.run(ask_knowledge("Unanswerable?", "demo-org", repository=FakeRepository([])))
    assert "No relevant information" in result["answer"]
    assert result["sources"] == []


def test_search_uses_org_scope():
    store = FakeRepository([{"source": "guide.txt", "text": "Consult the runbook."}])
    matches = search_knowledge("runbook", "orgA", kb="ops", limit=2, repository=store)
    assert len(matches) == 1
    assert store.calls == [("orgA", "ops", "runbook", 2)]
    assert "guide.txt" in telegram_search(matches)


def test_validation():
    with pytest.raises(ValueError):
        search_knowledge("", "orgA", repository=FakeRepository([]))
    with pytest.raises(ValueError):
        search_knowledge("question", "", repository=FakeRepository([]))
    with pytest.raises(ValueError):
        search_knowledge("question", "org", kb="../other", repository=FakeRepository([]))


def test_local_and_cloud_answering_use_same_module(monkeypatch):
    store = FakeRepository([{"source": "file.txt", "document_id": "x", "text": "blue", "chunk_id": "0"}])

    async def model(question, matches, settings):
        return "blue"

    monkeypatch.setattr("rag.answer", model)
    data = asyncio.run(ask_knowledge("What color?", "org", repository=store))
    assert data["answer"] == "blue"
    assert data["sources"][0]["source"] == "file.txt"
