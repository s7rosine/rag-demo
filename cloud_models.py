"""Provider-independent generation and embedding interfaces.

The provider is selected at runtime; no model credentials are committed.
Embedding results are not yet stored in pgvector. This module introduces
the interface needed for a future vector indexing migration.
"""
from __future__ import annotations

import os
from urllib.parse import quote

import httpx



class ModelProviderError(Exception):
    """Sanitized model failure: does not carry API response text or credentials."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _provider_failure(exc: Exception) -> ModelProviderError:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return ModelProviderError("invalid_key")
        if status == 403:
            return ModelProviderError("access_denied")
        if status == 402:
            return ModelProviderError("billing_required")
        if status == 404:
            return ModelProviderError("model_unavailable")
        if status == 429:
            try:
                details = exc.response.json().get("error", {})
                code = details.get("code") if isinstance(details, dict) else None
            except (ValueError, TypeError, AttributeError):
                code = None
            if code == "insufficient_quota":
                return ModelProviderError("quota_exhausted")
            return ModelProviderError("rate_limited_or_quota")
        if status == 400:
            return ModelProviderError("invalid_request")
        if status >= 500:
            return ModelProviderError("service_unavailable")
        return ModelProviderError("provider_error")
    if isinstance(exc, httpx.TimeoutException):
        return ModelProviderError("timeout")
    if isinstance(exc, httpx.RequestError):
        return ModelProviderError("network_error")
    return ModelProviderError("invalid_response")


def model_error_message(reason: str) -> str:
    """Only known status categories are displayed; no upstream error text."""
    messages = {
        "invalid_key": "OpenAI rejected the API key (401). Check LLM_API_KEY in Vercel.",
        "access_denied": "OpenAI denied the request (403). Check project API permissions.",
        "billing_required": "OpenAI requires billing or credits (402). Check API billing.",
        "quota_exhausted": "OpenAI API quota exhausted (429). Check API project billing and credits.",
        "rate_limited_or_quota": "OpenAI returned 429. Check rate limits, credits and billing.",
        "model_unavailable": "Requested model is unavailable (404). Check LLM_MODEL.",
        "invalid_request": "OpenAI rejected the request (400). Check model and API parameters.",
        "service_unavailable": "Model provider temporarily unavailable (5xx). Retry later.",
        "timeout": "Model provider timed out. Retry later.",
        "network_error": "Could not reach model provider. Check API endpoint.",
        "invalid_response": "Model provider returned an unexpected response format.",
        "provider_error": "Model provider rejected the request. Check configuration.",
    }
    return messages.get(reason, "AI generation failed. Check your model configuration.")


def _https(url: str) -> str:
    url = url.rstrip("/")
    if not url.startswith("https://") and not url.startswith("http://localhost:"):
        raise ValueError("Model endpoint must use HTTPS or localhost")
    return url


def _config(var: str, fallback: str = "") -> str:
    return os.getenv(var, fallback)


async def generate(system: str, question: str, *, provider: str | None = None,
                   model: str | None = None, base_url: str | None = None,
                   api_key: str | None = None) -> str:
    """Generate from the exact supplied context and question.

    Supported providers: openai_compatible (OpenAI, OpenRouter, NIM),
    anthropic (native Messages API), gemini (native generateContent).
    """
    provider = (provider or _config("LLM_PROVIDER", "openai_compatible")).lower()
    model = model or _config("LLM_MODEL")
    key = api_key if api_key is not None else _config("LLM_API_KEY")
    if not model:
        raise ValueError("LLM_MODEL is not configured")
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            if provider == "openai_compatible":
                url = _https(base_url or _config("LLM_BASE_URL"))
                response = await client.post(
                    url + "/chat/completions",
                    headers={"Authorization": "Bearer " + key} if key else {},
                    json={"model": model, "temperature": 0,
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": question}]},
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            if provider == "anthropic":
                if not key:
                    raise ValueError("LLM_API_KEY is required for Anthropic")
                response = await client.post(
                    _https(base_url or "https://api.anthropic.com/v1") + "/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                    json={"model": model, "max_tokens": 1024, "system": system,
                          "messages": [{"role": "user", "content": question}]},
                )
                response.raise_for_status()
                return "".join(c.get("text", "") for c in response.json()["content"]
                               if c.get("type") == "text")
            if provider == "gemini":
                if not key:
                    raise ValueError("LLM_API_KEY is required for Gemini")
                response = await client.post(
                    _https(base_url or "https://generativelanguage.googleapis.com/v1beta")
                    + "/models/" + quote(model, safe="") + ":generateContent",
                    headers={"x-goog-api-key": key},
                    json={"system_instruction": {"parts": [{"text": system}]},
                          "contents": [{"role": "user", "parts": [{"text": question}]}]},
                )
                response.raise_for_status()
                return "".join(p.get("text", "") for c in response.json()["candidates"]
                               for p in c.get("content", {}).get("parts", []))
            raise ValueError("Unsupported LLM_PROVIDER")
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise _provider_failure(exc) from None
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise _provider_failure(exc) from None


async def embed_texts(texts: list[str], *, provider: str | None = None,
                      model: str | None = None, base_url: str | None = None,
                      api_key: str | None = None) -> list[list[float]]:
    """Obtain embeddings independently from the generation provider.

    A future migration can persist these vectors using pgvector; the existing
    cloud search remains keyword-based until that migration is applied.
    """
    if not texts or any(not s for s in texts) or len(texts) > 100:
        raise ValueError("Provide 1–100 nonempty texts")
    provider = (provider or _config("EMBEDDING_PROVIDER", "openai_compatible")).lower()
    model = model or _config("EMBEDDING_MODEL")
    if provider != "openai_compatible":
        raise ValueError("Embedding provider not implemented: use openai_compatible")
    if not model:
        raise ValueError("EMBEDDING_MODEL is not configured")
    key = api_key if api_key is not None else _config("EMBEDDING_API_KEY")
    url = _https(base_url or _config("EMBEDDING_BASE_URL"))
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        response = await client.post(
            url + "/embeddings",
            headers={"Authorization": "Bearer " + key} if key else {},
            json={"model": model, "input": texts},
        )
        response.raise_for_status()
        data = response.json()["data"]
        vectors = [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
        if len(vectors) != len(texts):
            raise ValueError("Embedding response count mismatch")
        return vectors
