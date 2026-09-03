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
    models = r.json()["models"]
    assert len(models) > 0
    assert any(m["id"] == "llama-3.3-70b-versatile" for m in models)
    assert all(m["provider"] == "Groq" for m in models)


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


def test_signup_and_login():
    email = f"test-{__import__('uuid').uuid4().hex[:6]}@test.com"

    # Signup
    r = client.post("/api/auth/signup", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token

    # Login
    r = client.post("/api/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200
    assert r.json()["token"]

    # Auth'd me
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email

    # Unauthenticated me
    r = client.get("/api/auth/me")
    assert r.status_code == 401

    # Bad password
    r = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 401


def test_rag_pipeline_helpers():
    from rag.pipeline import process_pipeline_chunks
    from rag.rerank import rerank_chunks

    # Test process_pipeline_chunks with empty doc_ids
    chunks, count = process_pipeline_chunks("query", [])
    assert chunks == []
    assert count >= 1

    # Test rerank_chunks with small list
    sample_chunks = [
        {"text": "Chunk 1", "score": 0.5},
        {"text": "Chunk 2", "score": 0.8},
    ]
    reranked = rerank_chunks("test query", sample_chunks, top_k=6)
    assert len(reranked) == 2

