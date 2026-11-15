"""Cloud-friendly RAG question answering shared by FastAPI and Telegram.

This module deliberately reuses the existing PostgreSQL/SQLite repository and
OpenAI-compatible provider. It does not silently index sample data or use
ephemeral storage for production questions.
"""
from __future__ import annotations

from typing import Any

from platform_core import Repository, Settings, answer


def _validate(question: str, org: str, kb: str, limit: int) -> str:
    if not org:
        raise ValueError("Organization must be configured")
    if not kb or len(kb) > 64 or not kb.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Invalid knowledge base")
    if not 1 <= limit <= 20:
        raise ValueError("Retrieval limit must be between 1 and 20")
    cleaned = question.strip()
    if not cleaned or len(cleaned) > 2000:
        raise ValueError("Question must contain 1 to 2000 characters")
    return cleaned


def search_knowledge(
    question: str,
    org: str,
    kb: str = "default",
    limit: int = 4,
    repository: Repository | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Retrieve source-attributed chunks for the authorized organization."""
    question = _validate(question, org, kb, limit)
    repository = repository or Repository(settings or Settings())
    return repository.search(org, kb, question, limit)


async def ask_knowledge(
    question: str,
    org: str,
    kb: str = "default",
    limit: int = 4,
    repository: Repository | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Answer a question with source provenance from durable indexed content."""
    question = _validate(question, org, kb, limit)
    settings = settings or Settings()
    matches = search_knowledge(
        question, org, kb, limit, repository=repository, settings=settings,
    )
    response = await answer(question, matches, settings)
    seen: set[tuple[str, str]] = set()
    citations = []
    for match in matches:
        item = (
            str(match.get("source", "unknown")),
            str(match.get("document_id", "")),
        )
        if item in seen:
            continue
        seen.add(item)
        citations.append({"source": item[0], "document_id": item[1]})
    return {"answer": response, "sources": citations, "knowledge_base": kb}


def telegram_answer(result: dict[str, Any]) -> str:
    """Return a readable Telegram reply without exposing internal identifiers."""
    message = str(result["answer"]).strip()
    filenames = list(dict.fromkeys(
        str(item.get("source", "")) for item in result.get("sources", [])
        if item.get("source")
    ))
    if filenames:
        message += "\n\nSources: " + ", ".join(filenames[:6])
    # Telegram messages may not exceed 4096 chars; leave room for transport.
    return message[:3800]


def telegram_search(matches: list[dict[str, Any]]) -> str:
    """Format search hits with source names, not document internals."""
    if not matches:
        return "No matching information was found in the selected knowledge base."
    lines = ["Matching document excerpts:"]
    for match in matches[:5]:
        source = str(match.get("source", "unknown"))
        excerpt = str(match.get("text", "")).replace("\n", " ")[:230]
        lines.append(f"• {source}: {excerpt}")
    return "\n".join(lines)[:3800]
