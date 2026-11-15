"""Read-only, bounded cloud source connectors for the RAG ingestion pipeline.

Connectors return document bytes; they never write to or delete from source systems.
Imports are lazy so optional cloud SDKs are not required for the FastAPI runtime.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import quote

import httpx

MAX_BYTES = 8_000_000
ALLOWED_SUFFIXES = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".docx", ".pdf"}


@dataclass(frozen=True)
class SourceDocument:
    source: str
    filename: str
    data: bytes


def _file_ok(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in ALLOWED_SUFFIXES


def _limit(data: bytes) -> bytes:
    if len(data) > MAX_BYTES:
        raise ValueError("Source document exceeds 8 MB")
    return data


def s3_documents(bucket: str, prefix: str = "", limit: int = 50) -> Iterable[SourceDocument]:
    """S3 objects in a configured bucket/prefix; uses AWS default credential chain.

    Requires optional boto3. No bucket enumeration outside the configured prefix.
    """
    if not bucket or not 1 <= limit <= 500:
        raise ValueError("S3 bucket and bounded limit required")
    import boto3

    client = boto3.client("s3", region_name=os.getenv("AWS_REGION") or None)
    emitted = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, PaginationConfig={"PageSize": 100}):
        for item in page.get("Contents", []):
            key = item["Key"]
            if not _file_ok(key) or item.get("Size", 0) > MAX_BYTES:
                continue
            result = client.get_object(Bucket=bucket, Key=key)
            try:
                data = _limit(result["Body"].read(MAX_BYTES + 1))
            finally:
                result["Body"].close()
            yield SourceDocument(source="s3://" + bucket + "/" + key, filename=key, data=data)
            emitted += 1
            if emitted >= limit:
                return


def _notion_text(block: dict) -> str:
    kind = block.get("type", "")
    node = block.get(kind) or {}
    if kind == "child_page":
        return str(node.get("title", ""))
    return "".join(part.get("plain_text", "") for part in node.get("rich_text", []))


def notion_documents(token: str, page_ids: list[str], limit: int = 30) -> Iterable[SourceDocument]:
    """Read explicitly shared Notion pages and their nested block text.

    Does not auto-discover workspace pages or query databases.
    Requires integration access to all requested page IDs.
    """
    if not token or not 1 <= limit <= 100:
        raise ValueError("Notion token and bounded limit required")
    headers = {"Authorization": "Bearer " + token, "Notion-Version": "2022-06-28"}
    base = "https://api.notion.com/v1/blocks/"
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        for page_id in page_ids[:limit]:
            page_id = page_id.strip()
            if not page_id or not all(c.isalnum() or c == "-" for c in page_id):
                raise ValueError("Invalid Notion page ID")
            fragments: list[str] = []
            def walk(block_id: str, depth: int = 0) -> None:
                if depth > 5:
                    return
                cursor = None
                while True:
                    params = {"page_size": 100}
                    if cursor:
                        params["start_cursor"] = cursor
                    response = client.get(base + quote(block_id, safe="-") + "/children", params=params)
                    response.raise_for_status()
                    body = response.json()
                    for block in body.get("results", []):
                        text = _notion_text(block)
                        if text:
                            fragments.append(text)
                        if block.get("has_children"):
                            walk(block["id"], depth + 1)
                        if sum(len(v) for v in fragments) > MAX_BYTES:
                            raise ValueError("Notion page exceeds size limit")
                    cursor = body.get("next_cursor") if body.get("has_more") else None
                    if not cursor:
                        break
            walk(page_id)
            content = "\n".join(fragments).encode("utf-8")
            if content.strip():
                yield SourceDocument("notion://" + page_id, page_id + ".md", _limit(content))


def drive_documents(service_account_json: str, folder_id: str, limit: int = 50) -> Iterable[SourceDocument]:
    """List direct children of one allowed Drive folder; Google Docs export to text.

    Uses service-account credentials supplied at runtime. Native spreadsheets,
    presentations, shortcuts, and nested folders are deliberately not indexed.
    """
    if not service_account_json or not folder_id or not 1 <= limit <= 500:
        raise ValueError("Drive credentials, folder ID, and bounded limit required")
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(service_account_json),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    session = AuthorizedSession(credentials)
    base = "https://www.googleapis.com/drive/v3/files"
    page_token = None
    emitted = 0
    safe_folder = folder_id.replace("\\", "\\\\").replace("'", "\\'")
    try:
        while True:
            params = {
                "q": "'" + safe_folder + "' in parents and trashed = false",
                "fields": "nextPageToken,files(id,name,mimeType,size)",
                "page_size": 100,
                "pageSize": 100,
            }
            params.pop("page_size")
            if page_token:
                params["pageToken"] = page_token
            response = session.get(base, params=params, timeout=20)
            response.raise_for_status()
            body = response.json()
            for file in body.get("files", []):
                file_id = file.get("id")
                name = file.get("name", "")
                mime = file.get("mimeType", "")
                if not file_id:
                    continue
                if mime == "application/vnd.google-apps.document":
                    response = session.get(base + "/" + quote(file_id, safe="") + "/export",
                                           params={"mimeType": "text/plain"}, timeout=30)
                    name += ".txt"
                elif _file_ok(name) and int(file.get("size", 0)) <= MAX_BYTES:
                    response = session.get(base + "/" + quote(file_id, safe=""),
                                           params={"alt": "media"}, timeout=30)
                else:
                    continue
                response.raise_for_status()
                data = _limit(response.content)
                yield SourceDocument("gdrive://" + file_id, name, data)
                emitted += 1
                if emitted >= limit:
                    return
            page_token = body.get("nextPageToken")
            if not page_token:
                return
    finally:
        session.close()


def configured_documents(source: str, limit: int = 50) -> Iterable[SourceDocument]:
    """Explicitly opt in to one scoped source, never blanket-crawl accounts."""
    if source == "s3":
        bucket = os.getenv("S3_BUCKET", "")
        if not bucket:
            raise ValueError("S3_BUCKET is missing")
        return s3_documents(bucket, os.getenv("S3_PREFIX", ""), limit)
    if source == "notion":
        token = os.getenv("NOTION_API_TOKEN", "")
        ids = [x.strip() for x in os.getenv("NOTION_PAGE_IDS", "").split(",") if x.strip()]
        if not token or not ids:
            raise ValueError("NOTION_API_TOKEN and NOTION_PAGE_IDS required")
        return notion_documents(token, ids, limit)
    if source == "gdrive":
        return drive_documents(os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON", ""),
                               os.getenv("GDRIVE_FOLDER_ID", ""), limit)
    raise ValueError("Unknown source: expected s3, notion or gdrive")
