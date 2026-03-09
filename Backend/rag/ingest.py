import json
import pickle
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

from config import INDEXES_DIR, TEXTS_DIR
from utils.pdf_loader import extract_text_from_pdf, get_pdf_metadata
from utils.text_splitter import split_into_chunks
from config import CHUNK_SIZE, CHUNK_OVERLAP


def ingest_document(doc_id: str, pdf_path: Path) -> dict:
    """
    Full ingestion pipeline:
    1. Extract text from PDF
    2. Split into chunks
    3. Build TF-IDF index
    4. Save everything to disk
    Returns summary dict.
    """
    # Extract text
    raw_text = extract_text_from_pdf(pdf_path)
    metadata = get_pdf_metadata(pdf_path)

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

    # Save chunks
    texts_path = TEXTS_DIR / f"{doc_id}.json"
    with open(texts_path, "w", encoding="utf-8") as f:
        json.dump({"doc_id": doc_id, "metadata": metadata, "chunks": chunks}, f, ensure_ascii=False)

    # Save index
    index_path = INDEXES_DIR / f"{doc_id}.pkl"
    with open(index_path, "wb") as f:
        pickle.dump({"vectorizer": vectorizer, "matrix": tfidf_matrix}, f)

    return {
        "doc_id": doc_id,
        "chunk_count": len(chunks),
        "page_count": metadata["page_count"],
        "title": metadata["title"] or pdf_path.stem,
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
    for path in [
        INDEXES_DIR / f"{doc_id}.pkl",
        TEXTS_DIR / f"{doc_id}.json",
    ]:
        if path.exists():
            path.unlink()