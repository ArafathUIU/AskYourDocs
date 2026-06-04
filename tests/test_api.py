from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_documents_empty():
    r = client.get("/api/documents")
    assert r.status_code == 200
    assert "documents" in r.json()


def test_list_models():
    r = client.get("/api/models")
    assert r.status_code == 200
    assert len(r.json()["models"]) > 0


def test_list_chats():
    r = client.get("/api/chats")
    assert r.status_code == 200
    assert "chats" in r.json()


def test_create_chat():
    r = client.post("/api/chats", json={"title": "Test Chat"})
    assert r.status_code == 200
    data = r.json()
    assert "chat_id" in data
    chat_id = data["chat_id"]

    # Cleanup
    client.delete(f"/api/chats/{chat_id}")


def test_list_collections():
    r = client.get("/api/collections")
    assert r.status_code == 200


def test_list_prompts():
    r = client.get("/api/prompts")
    assert r.status_code == 200
    assert len(r.json()["prompts"]) > 0


def test_chat_without_docs():
    r = client.post("/api/chat", json={
        "query": "test",
        "doc_ids": [],
    })
    assert r.status_code == 400


def test_upload_invalid_file():
    # Simulate non-file upload
    r = client.post("/api/upload")
    assert r.status_code in (400, 422)


def test_document_not_found():
    r = client.delete("/api/documents/nonexistent")
    assert r.status_code == 404
