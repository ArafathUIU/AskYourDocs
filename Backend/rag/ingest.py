import json
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

from config import INDEXES_DIR, TEXTS_DIR
from utils.doc_loader import extract_text_from_file
from utils.text_splitter import split_into_chunks
from config import CHUNK_SIZE, CHUNK_OVERLAP


def ingest_document(doc_id: str, file_path: Path) -> dict:
    """
    Full ingestion pipeline:
    1. Extract text from file (PDF, DOCX, TXT, MD)
    2. Split into chunks
    3. Build TF-IDF index
    4. Build semantic embeddings
    5. Save everything to disk
    Returns summary dict.
    """
    # Extract text
    raw_text, metadata = extract_text_from_file(file_path)

    # Chunk
    chunks = split_into_chunks(raw_text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError("No text could be extracted from this PDF.")

    # Build TF-IDF
    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(
        max_features=20000,
        ngram_range=(1, 2),
        stop_words="english",
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)

    # Build semantic embeddings
    from rag.embeddings import build_embedding_index
    from rag.embeddings import embed_texts

    # Save chunks first (needed by build_embedding_index)
    texts_path = TEXTS_DIR / f"{doc_id}.json"
    with open(texts_path, "w", encoding="utf-8") as f:
        json.dump({"doc_id": doc_id, "metadata": metadata, "chunks": chunks}, f, ensure_ascii=False)

    # Build and save embeddings
    try:
        build_embedding_index(doc_id)
    except Exception:
        pass  # Embeddings are optional; TF-IDF still works

    # Save index
    index_path = INDEXES_DIR / f"{doc_id}.pkl"
    with open(index_path, "wb") as f:
        pickle.dump({"vectorizer": vectorizer, "matrix": tfidf_matrix}, f)

    return {
        "doc_id": doc_id,
        "chunk_count": len(chunks),
        "page_count": metadata["page_count"],
        "title": metadata["title"] or file_path.stem,
    }


def load_index(doc_id: str):
    """Load a pickled TF-IDF index."""
    index_path = INDEXES_DIR / f"{doc_id}.pkl"
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found for doc_id: {doc_id}")
    with open(index_path, "rb") as f:
        return pickle.load(f)


def load_chunks(doc_id: str) -> list[dict]:
    """Load text chunks for a document."""
    texts_path = TEXTS_DIR / f"{doc_id}.json"
    if not texts_path.exists():
        raise FileNotFoundError(f"Chunks not found for doc_id: {doc_id}")
    with open(texts_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]


def delete_document(doc_id: str):
    """Remove all stored data for a document."""
    from rag.embeddings import delete_embeddings

    for path in [
        INDEXES_DIR / f"{doc_id}.pkl",
        TEXTS_DIR / f"{doc_id}.json",
    ]:
        if path.exists():
            path.unlink()
    delete_embeddings(doc_id)