"""Cloud webhook registration is safe, idempotent and redacts failures."""
import asyncio

import telegram_registration as registration


def _call():
    return asyncio.run(registration.ensure_webhook(force=True))


def test_registration_when_unset(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    assert _call() == "not_configured"


def test_existing_webhook_not_reregistered(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test_secret")
    calls = []

    class Response:
        status_code = 200

        def json(self):
            return {"ok": True, "result": {"url": registration.DEFAULT_WEBHOOK}}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    monkeypatch.setattr(registration.httpx, "AsyncClient", Client)
    assert _call() == "registered"
    assert len(calls) == 1
    assert calls[0][0].endswith("/getWebhookInfo")


def test_registers_when_missing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "test_secret")
    calls = []

    class Response:
        status_code = 200

        def __init__(self, url=""):
            self.url = url

        def json(self):
            return {"ok": True, "result": {"url": self.url}}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response() if url.endswith("/getWebhookInfo") else Response()

    monkeypatch.setattr(registration.httpx, "AsyncClient", Client)
    assert _call() == "registered"
    assert len(calls) == 2
    assert calls[1][0].endswith("/setWebhook")
    assert calls[1][1]["data"]["secret_token"] == "test_secret"


def test_unavailable_does_not_expose_credentials(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "sensitive_test_token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "sensitive_test_secret")

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            raise RuntimeError("network failed: " + url)

    monkeypatch.setattr(registration.httpx, "AsyncClient", Client)
    # Errors not explicitly recognized by the connector must not be reflected
    # in public responses. RuntimeError is caught by the sanitized fail closed path.
    status = _call()
    assert status == "registration_unavailable"
    assert "sensitive" not in status


def test_invalid_custom_webhook_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "http://localhost:8000/telegram/webhook")
    assert _call() == "invalid_url"
