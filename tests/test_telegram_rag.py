"""Telegram webhook tests with no real Telegram requests."""
from fastapi.testclient import TestClient

import platform_app


def test_webhook_denies_unverified(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")
    response = TestClient(platform_app.app).post(
        "/telegram/webhook", json={"message": {"chat": {"id": 22}, "text": "/help"}},
    )
    assert response.status_code == 403


def test_webhook_ignores_other_chats(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    response = TestClient(platform_app.app).post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        json={"message": {"chat": {"id": 22}, "text": "hello"}},
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": False}


def test_help_command_without_db(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "22")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-test-token")
    sent = []

    class Reply:
        status_code = 200

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            sent.append(json)
            return Reply()

    monkeypatch.setattr(platform_app.httpx, "AsyncClient", FakeClient)
    response = TestClient(platform_app.app).post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        json={"message": {"chat": {"id": 22}, "text": "/help"}},
    )
    assert response.json() == {"accepted": True}
    assert "/ask" in sent[0]["text"]


def test_telegram_rag_question_route(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "22")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-test-token")
    monkeypatch.setenv("RAG_ORG", "org")
    monkeypatch.setenv("TELEGRAM_KNOWLEDGE_BASE", "manuals")
    sent = []

    async def fake_ask(question, org, kb, repository, settings):
        assert (question, org, kb) == ("Where is the guide?", "org", "manuals")
        return {"answer": "Look in the guide.", "sources": [{"source": "guide.md"}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            sent.append(json)
            return type("Result", (), {"status_code": 200})()

    monkeypatch.setattr(platform_app, "ask_knowledge", fake_ask)
    monkeypatch.setattr(platform_app.httpx, "AsyncClient", FakeClient)
    response = TestClient(platform_app.app).post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        json={"message": {"chat": {"id": 22}, "text": "/ask Where is the guide?"}},
    )
    assert response.status_code == 200
    assert sent[0]["text"] == "Look in the guide.\n\nSources: guide.md"

def test_status_command_is_restricted_to_authorized_chat(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "22")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("RAG_ORG", "test-org")
    sent = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, json):
            sent.append(json)
            return type("Reply", (), {"status_code": 200})()

    monkeypatch.setattr(platform_app.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(platform_app, "rag_status", lambda *args: "RAG diagnostics\\nDatabase: CONNECTED")
    client = TestClient(platform_app.app)
    verified = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={"message": {"chat": {"id": 22}, "text": "/status"}},
    )
    assert verified.json() == {"accepted": True}
    assert "Database: CONNECTED" in sent[0]["text"]
    unauthorized = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={"message": {"chat": {"id": 999}, "text": "/status"}},
    )
    assert unauthorized.json() == {"accepted": False}
    assert len(sent) == 1
