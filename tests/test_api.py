from fastapi.testclient import TestClient
from api import app

def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}

def test_empty_question_validation():
    assert TestClient(app).post("/query", json={"question": ""}).status_code == 422
