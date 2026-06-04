import json
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from config import DOCS_DIR, TEXTS_DIR, INDEXES_DIR, BASE_DIR, PROJECT_ROOT, LLM_MODEL
from rag.ingest import ingest_document, delete_document
from utils.doc_loader import get_supported_extensions, SUPPORTED_EXTENSIONS
from rag.pipeline import run_rag_pipeline
from rag.llm import generate_answer
from db import (
    add_document as db_add_doc, get_all_documents, get_document,
    delete_document_db, set_ingestion_status, create_chat, get_all_chats, get_chat,
    update_chat_title, delete_chat, get_chat_documents, add_message, get_messages,
    clear_messages, add_feedback, create_collection, get_all_collections,
    add_doc_to_collection, remove_doc_from_collection, get_collection_documents,
    delete_collection,
)

app = FastAPI(title="AskYourDocs API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = PROJECT_ROOT / "Frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Frontend Routes ──────────────────────────────────────────────────────────

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


@app.get("/viewer")
async def viewer_page():
    viewer = FRONTEND_DIR / "viewer.html"
    if viewer.exists():
        return FileResponse(str(viewer))
    raise HTTPException(404, "viewer.html not found")


# ── Document Routes ──────────────────────────────────────────────────────────

def _ingest_background(doc_id: str, doc_path: Path, filename: str):
    try:
        result = ingest_document(doc_id, doc_path)
        db_add_doc(doc_id, filename, result["chunk_count"], result["page_count"], result["title"])
        set_ingestion_status(doc_id, "ready")
    except Exception:
        set_ingestion_status(doc_id, "error")


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Supported: {', '.join(get_supported_extensions())}")

    doc_id = str(uuid.uuid4())[:8]
    doc_path = DOCS_DIR / f"{doc_id}{ext}"

    with open(doc_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Register immediately with processing status
    db_add_doc(doc_id, file.filename, 0, 0, file.filename)
    set_ingestion_status(doc_id, "processing")

    # Ingest in background
    if background_tasks:
        background_tasks.add_task(_ingest_background, doc_id, doc_path, file.filename)

    return {
        "doc_id": doc_id,
        "name": file.filename,
        "status": "processing",
        "message": "Document uploaded. Processing in background...",
    }


@app.get("/api/documents/{doc_id}/status")
async def document_status(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return {
        "doc_id": doc_id,
        "status": doc.get("ingestion_status", "ready"),
        "chunk_count": doc["chunk_count"],
        "page_count": doc["page_count"],
    }


@app.get("/api/documents")
async def list_documents():
    return {"documents": get_all_documents()}


@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")

    # Delete file with any supported extension
    for ext in get_supported_extensions():
        (DOCS_DIR / f"{doc_id}{ext}").unlink(missing_ok=True)

    delete_document(doc_id)
    delete_document_db(doc_id)

    return {"message": f"Document {doc_id} removed."}


@app.get("/api/documents/{doc_id}/download")
async def download_document(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")

    # Find file with any supported extension
    for ext in get_supported_extensions():
        file_path = DOCS_DIR / f"{doc_id}{ext}"
        if file_path.exists():
            media = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".txt": "text/plain",
                ".md": "text/markdown",
            }.get(ext, "application/octet-stream")
            return FileResponse(str(file_path), media_type=media, filename=doc["name"])

    raise HTTPException(404, "File not found.")


@app.get("/api/documents/{doc_id}/text")
async def download_text(doc_id: str, format: str = "txt"):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")

    texts_path = TEXTS_DIR / f"{doc_id}.json"
    if not texts_path.exists():
        raise HTTPException(404, "Text data not found.")

    with open(texts_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if format == "json":
        return JSONResponse(content=data)

    lines = []
    for chunk in data["chunks"]:
        lines.append(f"[Page {chunk['page']} | Chunk {chunk['chunk_index']+1}]")
        lines.append(chunk["text"])
        lines.append("")

    text_content = "\n".join(lines)
    doc_name = doc["name"].replace(".pdf", "")

    from fastapi.responses import Response
    return Response(
        content=text_content.encode("utf-8"),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{doc_name}_extracted.txt"'},
    )


# ── Chat Routes ──────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    doc_ids: list[str]
    chat_history: Optional[list[dict]] = None
    model: Optional[str] = None


class ChatCreateRequest(BaseModel):
    title: Optional[str] = "New Chat"
    doc_ids: Optional[list[str]] = None


class ChatTitleRequest(BaseModel):
    title: str


@app.post("/api/chats")
async def create_new_chat(req: ChatCreateRequest):
    chat_id = str(uuid.uuid4())[:8]
    result = create_chat(chat_id, req.title or "New Chat", req.doc_ids)
    return result


@app.get("/api/chats")
async def list_chats():
    return {"chats": get_all_chats()}


@app.get("/api/chats/{chat_id}")
async def get_chat_detail(chat_id: str):
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "Chat not found.")
    messages = get_messages(chat_id)
    doc_ids = get_chat_documents(chat_id)
    return {"chat": dict(chat), "messages": [dict(m) for m in messages], "doc_ids": doc_ids}


@app.patch("/api/chats/{chat_id}")
async def rename_chat(chat_id: str, req: ChatTitleRequest):
    update_chat_title(chat_id, req.title)
    return {"message": "Chat renamed."}


@app.delete("/api/chats/{chat_id}")
async def remove_chat(chat_id: str):
    delete_chat(chat_id)
    return {"message": "Chat deleted."}


class MessageCreate(BaseModel):
    role: str
    content: str
    sources: Optional[list[dict]] = None


@app.post("/api/chats/{chat_id}/messages")
async def save_message(chat_id: str, req: MessageCreate):
    msg_id = add_message(chat_id, req.role, req.content, req.sources)
    return {"message": "Message saved.", "id": msg_id}


@app.delete("/api/chats/{chat_id}/messages")
async def clear_chat_messages(chat_id: str):
    clear_messages(chat_id)
    return {"message": "Messages cleared."}


@app.get("/api/models")
async def list_models():
    return {
        "models": [
            {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "provider": "OpenCode Go"},
            {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "provider": "OpenCode Go"},
            {"id": "qwen3.7-plus", "name": "Qwen 3.7 Plus", "provider": "OpenCode Go"},
            {"id": "qwen3.7-max", "name": "Qwen 3.7 Max", "provider": "OpenCode Go"},
            {"id": "kimi-k2.6", "name": "Kimi K2.6", "provider": "OpenCode Go"},
            {"id": "mimo-v2.5", "name": "MiMo V2.5", "provider": "OpenCode Go"},
            {"id": "glm-5.1", "name": "GLM 5.1", "provider": "OpenCode Go"},
        ]
    }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty.")
    if not request.doc_ids:
        raise HTTPException(400, "Select at least one document.")

    docs = {d["doc_id"]: d for d in get_all_documents()}
    for doc_id in request.doc_ids:
        if doc_id not in docs:
            raise HTTPException(404, f"Document {doc_id} not found.")

    doc_names = {doc_id: docs[doc_id]["name"] for doc_id in request.doc_ids}

    result = run_rag_pipeline(
        query=request.query,
        doc_ids=request.doc_ids,
        doc_names=doc_names,
        chat_history=request.chat_history,
    )

    return result


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty.")
    if not request.doc_ids:
        raise HTTPException(400, "Select at least one document.")

    docs = {d["doc_id"]: d for d in get_all_documents()}
    for doc_id in request.doc_ids:
        if doc_id not in docs:
            raise HTTPException(404, f"Document {doc_id} not found.")

    doc_names = {doc_id: docs[doc_id]["name"] for doc_id in request.doc_ids}

    from rag.retrieve import retrieve_chunks

    chunks = retrieve_chunks(request.query, request.doc_ids)

    if not chunks:
        async def empty_stream():
            yield f"data: {json.dumps({'error': 'No relevant content found.'})}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    try:
        result = generate_answer(
            query=request.query,
            context_chunks=chunks,
            doc_names=doc_names,
            chat_history=request.chat_history,
            stream=True,
            model=request.model,
        )
    except Exception as e:
        async def error_stream():
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    stream = result["stream"]
    sources = result["sources"]

    async def token_stream():
        try:
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")


# ── Collection Routes ────────────────────────────────────────────────────────

class CollectionCreate(BaseModel):
    name: str


class CollectionDocAction(BaseModel):
    doc_id: str


@app.post("/api/collections")
async def new_collection(req: CollectionCreate):
    col_id = str(uuid.uuid4())[:8]
    return create_collection(col_id, req.name)


@app.get("/api/collections")
async def list_collections():
    return {"collections": get_all_collections()}


@app.delete("/api/collections/{col_id}")
async def remove_collection(col_id: str):
    delete_collection(col_id)
    return {"message": "Collection deleted."}


@app.post("/api/collections/{col_id}/documents")
async def add_to_collection(col_id: str, req: CollectionDocAction):
    add_doc_to_collection(col_id, req.doc_id)
    return {"message": "Document added to collection."}


@app.delete("/api/collections/{col_id}/documents/{doc_id}")
async def remove_from_collection(col_id: str, doc_id: str):
    remove_doc_from_collection(col_id, doc_id)
    return {"message": "Document removed from collection."}


@app.get("/api/collections/{col_id}/documents")
async def list_collection_docs(col_id: str):
    return {"doc_ids": get_collection_documents(col_id)}


# ── Feedback ─────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    message_id: int
    rating: str  # "up" or "down"


@app.post("/api/chats/{chat_id}/feedback")
async def submit_feedback(chat_id: str, req: FeedbackRequest):
    add_feedback(chat_id, req.message_id, req.rating)
    return {"message": "Feedback recorded."}


# ── Export ───────────────────────────────────────────────────────────────────

@app.get("/api/chats/{chat_id}/export")
async def export_chat(chat_id: str):
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "Chat not found.")
    messages = get_messages(chat_id)

    md_lines = [f"# {chat['title']}", "", f"*Exported from AskYourDocs*", ""]
    for m in messages:
        role = "**You**" if m["role"] == "user" else "**AI**"
        md_lines.append(f"### {role}")
        md_lines.append(m["content"])
        if m.get("sources"):
            try:
                sources = json.loads(m["sources"])
                for s in sources:
                    md_lines.append(f"> Source: {s['doc_name']}, page {s['page']}")
            except Exception:
                pass
        md_lines.append("")

    markdown = "\n".join(md_lines)

    from fastapi.responses import Response
    safe_title = "".join(c for c in chat["title"] if c.isalnum() or c in " _-").rstrip()
    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_title or "chat"}.md"'},
    )


# ── Prompt Library ────────────────────────────────────────────────────────────

PROMPT_LIBRARY = [
    {"id": "summarize", "label": "Summarize", "prompt": "Summarize the key points of this document."},
    {"id": "conclusions", "label": "Main Conclusions", "prompt": "What are the main conclusions or takeaways?"},
    {"id": "recommend", "label": "Recommendations", "prompt": "List all recommendations mentioned in the document."},
    {"id": "methodology", "label": "Methodology", "prompt": "What methodology or approach was used?"},
    {"id": "compare", "label": "Compare Sections", "prompt": "Compare and contrast the different sections or arguments."},
    {"id": "definitions", "label": "Definitions", "prompt": "List all key terms and their definitions found in the document."},
    {"id": "action-items", "label": "Action Items", "prompt": "Extract all action items, tasks, or next steps mentioned."},
    {"id": "timeline", "label": "Timeline", "prompt": "What is the timeline or sequence of events described?"},
    {"id": "pros-cons", "label": "Pros & Cons", "prompt": "What are the pros and cons or advantages and disadvantages discussed?"},
    {"id": "counter", "label": "Counter-arguments", "prompt": "What counter-arguments or opposing viewpoints are presented?"},
    {"id": "bullet-summary", "label": "Bullet Summary", "prompt": "Give me a bullet-point summary of the entire document."},
    {"id": "elaborate", "label": "Elaborate On", "prompt": ""},  # user fills in
]


@app.get("/api/prompts")
async def list_prompts():
    return {"prompts": PROMPT_LIBRARY}


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    docs = get_all_documents()
    return {"status": "ok", "documents_loaded": len(docs), "model": LLM_MODEL}
