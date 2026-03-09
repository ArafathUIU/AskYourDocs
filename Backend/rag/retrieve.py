import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from rag.ingest import load_index, load_chunks
from config import TOP_K_CHUNKS


def retrieve_chunks(query: str, doc_ids: list[str], top_k: int = TOP_K_CHUNKS) -> list[dict]:
    """
    Retrieve top-k relevant chunks from one or more documents.
    Returns list of {text, page, doc_id, score} dicts.
    """
    if not doc_ids:
        return []

    all_results = []

    for doc_id in doc_ids:
        try:
            index_data = load_index(doc_id)
            chunks = load_chunks(doc_id)
        except FileNotFoundError:
            continue

        vectorizer = index_data["vectorizer"]
        matrix = index_data["matrix"]

        # Transform query
        query_vec = vectorizer.transform([query])
        scores = cosine_similarity(query_vec, matrix).flatten()

        # Get top results
        top_indices = np.argsort(scores)[::-1][:top_k]
        for idx in top_indices:
            if scores[idx] > 0.01:  # Minimum relevance threshold
                all_results.append({
                    "text": chunks[idx]["text"],
                    "page": chunks[idx]["page"],
                    "doc_id": doc_id,
                    "score": float(scores[idx]),
                })

    # Sort all results by score and return top_k
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:top_k]