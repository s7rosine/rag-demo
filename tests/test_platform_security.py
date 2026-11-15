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
