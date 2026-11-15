"""Register Telegram's cloud webhook without local commands or logged credentials.

Works during FastAPI lifespan startup; /health is a safe cold-start fallback.
Never logs Telegram API URLs, third-party exceptions or secret values.
"""
import os
import time
from urllib.parse import urlsplit

import httpx

DEFAULT_WEBHOOK = "https://rag-demo-muku-solutions.vercel.app/telegram/webhook"
CHECK_INTERVAL_SECONDS = 120
_next_check = 0.0
_current_status = "not_checked"


def webhook_status() -> str:
    """Public, sanitized status; does not expose tokens or Telegram details."""
    return _current_status


async def ensure_webhook(force: bool = False) -> str:
    """Idempotently point Telegram to the configured Vercel webhook.

    Failure never blocks API startup and never raises a token-bearing HTTP error.
    """
    global _next_check, _current_status

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    destination = os.getenv("TELEGRAM_WEBHOOK_URL", DEFAULT_WEBHOOK)

    if not bot_token or not secret:
        _current_status = "not_configured"
        return _current_status

    parts = urlsplit(destination)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password or (
        parts.path != "/telegram/webhook" or parts.query or parts.fragment
    ):
        _current_status = "invalid_url"
        return _current_status

    now = time.monotonic()
    if not force and now < _next_check:
        return _current_status
    _next_check = now + CHECK_INTERVAL_SECONDS

    # The Telegram Bot API requires the bot token in the HTTPS request path.
    # Never log URLs, response bodies, request exceptions, or HTTP client debug output.
    base = "https://api.telegram.org/bot" + bot_token
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            current = await client.post(base + "/getWebhookInfo")
            if current.status_code != 200:
                _current_status = "registration_unavailable"
                return _current_status
            data = current.json()
            if not data.get("ok"):
                _current_status = "registration_unavailable"
                return _current_status
            if (data.get("result") or {}).get("url") == destination:
                _current_status = "registered"
                return _current_status

            result = await client.post(
                base + "/setWebhook",
                data={
                    "url": destination,
                    "secret_token": secret,
                    "allowed_updates": '["message"]',
                    "drop_pending_updates": "false",
                },
            )
            if result.status_code == 200 and result.json().get("ok") is True:
                _current_status = "registered"
            else:
                _current_status = "registration_unavailable"
    except Exception:  # Never propagate token-bearing third-party errors.
        # Do not log or return the original exception.
        _current_status = "registration_unavailable"
    return _current_status
