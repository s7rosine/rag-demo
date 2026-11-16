from fastapi.testclient import TestClient
import platform_app

client = TestClient(platform_app.app)

def test_health_is_public():
    assert client.get("/health").status_code == 200

def test_read_is_denied_without_token():
    assert client.get("/knowledge-bases").status_code == 401

def test_ingest_denied_without_token():
    assert client.post("/ingest", files={"file": ("a.txt", b"secret")}).status_code == 401

def test_telegram_requires_secret():
    assert client.post("/telegram/webhook", json={"message": {"text": "Hi"}}).status_code == 403

def test_invalid_read_token_never_reflected(monkeypatch):
    monkeypatch.setenv("RAG_READ_TOKEN", "correct-secret")
    invalid = "exfiltrate-this"
    response = client.get("/knowledge-bases", headers={"Authorization": "Bearer " + invalid})
    assert response.status_code == 403
    assert invalid not in response.text
    assert "correct-secret" not in response.text


def test_swagger_exposes_bearer_scheme():
    """Swagger must show Authorize, not a free-text authorization header."""
    schema = client.get("/openapi.json").json()
    bearer = schema["components"]["securitySchemes"]["RAGBearerAuth"]
    assert bearer["type"] == "http"
    assert bearer["scheme"] == "bearer"
    operation = schema["paths"]["/admin/sync/notion"]["post"]
    assert {"RAGBearerAuth": []} in operation["security"]
    assert not any(p["name"].lower() == "authorization" for p in operation.get("parameters", []))


def test_write_token_is_recognized_but_notion_page_is_scoped(monkeypatch):
    monkeypatch.setenv("RAG_WRITE_TOKEN", "secure-test-write-token")
    monkeypatch.setenv("RAG_ORG", "test-org")
    monkeypatch.setenv("NOTION_API_TOKEN", "fake-test-notion")
    monkeypatch.setenv("NOTION_PAGE_IDS", "approved-page-123")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake-host/test")
    response = client.post(
        "/admin/sync/notion",
        headers={"Authorization": "Bearer secure-test-write-token"},
        json={"page_id": "unapproved-page"},
    )
    assert response.status_code == 403


def test_wrong_write_token_rejected(monkeypatch):
    monkeypatch.setenv("RAG_WRITE_TOKEN", "correct-private-token")
    response = client.post(
        "/admin/sync/notion",
        headers={"Authorization": "Bearer wrong-token"},
        json={"page_id": "approved-page-123"},
    )
    assert response.status_code == 403
    assert "correct-private-token" not in response.text
