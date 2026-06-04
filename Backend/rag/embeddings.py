import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

from config import TEXTS_DIR, INDEXES_DIR

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def embed_texts(texts: list[str]) -> np.ndarray:
    model = get_embedding_model()
    return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)


def embed_query(query: str) -> np.ndarray:
    model = get_embedding_model()
    return model.encode([query], show_progress_bar=False, convert_to_numpy=True)[0]


def build_embedding_index(doc_id: str):
    chunks_path = TEXTS_DIR / f"{doc_id}.json"
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks not found for doc_id: {doc_id}")

    with open(chunks_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts = [c["text"] for c in data["chunks"]]
    embeddings = embed_texts(texts)

    emb_path = INDEXES_DIR / f"{doc_id}_emb.npy"
    np.save(emb_path, embeddings)


def load_embeddings(doc_id: str) -> np.ndarray:
    emb_path = INDEXES_DIR / f"{doc_id}_emb.npy"
    if not emb_path.exists():
        raise FileNotFoundError(f"Embeddings not found for doc_id: {doc_id}")
    return np.load(emb_path)


def delete_embeddings(doc_id: str):
    emb_path = INDEXES_DIR / f"{doc_id}_emb.npy"
    if emb_path.exists():
        emb_path.unlink()


def hybrid_score(tfidf_score: float, semantic_score: float, alpha: float = 0.5) -> float:
    return alpha * tfidf_score + (1 - alpha) * semantic_score
