import json
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import DOCS_DIR, TEXTS_DIR, INDEXES_DIR, BASE_DIR
from rag.ingest import ingest_document, delete_document
from rag.pipeline import run_rag_pipeline

app = FastAPI(title="AskYourDocs API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = BASE_DIR.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Registry: doc_id → {name, path, chunk_count, page_count} ──────────────────
REGISTRY_PATH = DOCS_DIR / "_registry.json"


def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    return {}


def save_registry(registry: dict):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "AskYourDocs API running"}


@app.get("/chat-page")
async def chat_page():
    chat = FRONTEND_DIR / "chat.html"
    if chat.exists():
        return FileResponse(str(chat))
    raise HTTPException(404, "chat.html not found")


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and ingest a PDF document."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    doc_id = str(uuid.uuid4())[:8]
    pdf_path = DOCS_DIR / f"{doc_id}.pdf"

    # Save PDF
    with open(pdf_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Ingest
    try:
        result = ingest_document(doc_id, pdf_path)
    except Exception as e:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Ingestion failed: {str(e)}")

    # Update registry
    registry = load_registry()
    registry[doc_id] = {
        "name": file.filename,
        "doc_id": doc_id,
        "chunk_count": result["chunk_count"],
        "page_count": result["page_count"],
        "title": result["title"],
    }
    save_registry(registry)

    return {
        "doc_id": doc_id,
        "name": file.filename,
        "chunk_count": result["chunk_count"],
        "page_count": result["page_count"],
        "message": "Document ingested successfully.",
    }


@app.get("/api/documents")
async def list_documents():
    """List all available documents."""
    registry = load_registry()
    return {"documents": list(registry.values())}


@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str):
    """Remove a document and all its data."""
    registry = load_registry()
    if doc_id not in registry:
        raise HTTPException(404, "Document not found.")

    # Delete files
    pdf_path = DOCS_DIR / f"{doc_id}.pdf"
    pdf_path.unlink(missing_ok=True)
    delete_document(doc_id)

    # Update registry
    del registry[doc_id]
    save_registry(registry)

    return {"message": f"Document {doc_id} removed."}


@app.get("/api/documents/{doc_id}/download")
async def download_document(doc_id: str):
    """Download original PDF."""
    registry = load_registry()
    if doc_id not in registry:
        raise HTTPException(404, "Document not found.")

    pdf_path = DOCS_DIR / f"{doc_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "PDF file not found.")

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=registry[doc_id]["name"],
    )


@app.get("/api/documents/{doc_id}/text")
async def download_text(doc_id: str, format: str = "txt"):
    """Download extracted text as .txt or .json."""
    registry = load_registry()
    if doc_id not in registry:
        raise HTTPException(404, "Document not found.")

    texts_path = TEXTS_DIR / f"{doc_id}.json"
    if not texts_path.exists():
        raise HTTPException(404, "Text data not found.")

    with open(texts_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if format == "json":
        return JSONResponse(content=data)

    # Plain text export
    lines = []
    for chunk in data["chunks"]:
        lines.append(f"[Page {chunk['page']} | Chunk {chunk['chunk_index']+1}]")
        lines.append(chunk["text"])
        lines.append("")

    text_content = "\n".join(lines)
    doc_name = registry[doc_id]["name"].replace(".pdf", "")

    from fastapi.responses import Response
    return Response(
        content=text_content.encode("utf-8"),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{doc_name}_extracted.txt"'},
    )


class ChatRequest(BaseModel):
    query: str
    doc_ids: list[str]
    chat_history: Optional[list[dict]] = None


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Main RAG chat endpoint."""
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty.")
    if not request.doc_ids:
        raise HTTPException(400, "Select at least one document.")

    registry = load_registry()
    doc_names = {
        doc_id: registry.get(doc_id, {}).get("name", doc_id)
        for doc_id in request.doc_ids
    }

    # Validate doc_ids
    for doc_id in request.doc_ids:
        if doc_id not in registry:
            raise HTTPException(404, f"Document {doc_id} not found.")

    result = run_rag_pipeline(
        query=request.query,
        doc_ids=request.doc_ids,
        doc_names=doc_names,
        chat_history=request.chat_history,
    )

    return result


@app.get("/api/health")
async def health():
    registry = load_registry()
    return {"status": "ok", "documents_loaded": len(registry)}