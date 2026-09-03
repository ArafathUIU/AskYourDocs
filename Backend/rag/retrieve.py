import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from rag.ingest import load_index, load_chunks
from config import TOP_K_CHUNKS


def retrieve_chunks(query: str, doc_ids: list[str], top_k: int = TOP_K_CHUNKS) -> list[dict]:
    """
    Retrieve top-k relevant chunks from one or more documents using hybrid search.
    Falls back to returning first chunks if no match found.
    Returns list of {text, page, doc_id, score} dicts.
    """
    if not doc_ids:
        return []

    all_results = []
    all_chunks_by_doc = {}

    query_emb = None
    try:
        from rag.embeddings import embed_query
        query_emb = embed_query(query).reshape(1, -1)
    except Exception:
        pass

    for doc_id in doc_ids:
        try:
            index_data = load_index(doc_id)
            chunks = load_chunks(doc_id)
        except FileNotFoundError:
            continue

        all_chunks_by_doc[doc_id] = chunks
        vectorizer = index_data["vectorizer"]
        matrix = index_data["matrix"]

        # TF-IDF scores
        query_vec = vectorizer.transform([query])
        tfidf_scores = cosine_similarity(query_vec, matrix).flatten()
        tfidf_scores = np.clip(tfidf_scores, 0, 1)

        # Semantic scores (if embeddings exist and load successfully)
        has_semantic = False
        semantic_scores = np.zeros(len(tfidf_scores))
        if query_emb is not None:
            try:
                from rag.embeddings import load_embeddings
                embeddings = load_embeddings(doc_id)
                semantic_scores = cosine_similarity(query_emb, embeddings).flatten()
                semantic_scores = np.clip(semantic_scores, 0, 1)
                has_semantic = True
            except Exception:
                pass

        # Hybrid fusion (both cosine scores are in [0, 1])
        alpha = 0.6 if has_semantic else 1.0
        hybrid_scores = alpha * tfidf_scores + (1 - alpha) * semantic_scores

        # Get top results
        top_indices = np.argsort(hybrid_scores)[::-1][:top_k]
        for idx in top_indices:
            all_results.append({
                "text": chunks[idx]["text"],
                "page": chunks[idx]["page"],
                "doc_id": doc_id,
                "score": float(hybrid_scores[idx]),
                "tfidf_score": float(tfidf_scores[idx]),
                "semantic_score": float(semantic_scores[idx]) if has_semantic else 0,
            })


    if all_results:
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    # Fallback: no semantic match found, return first chunk from each doc
    fallback = []
    for doc_id in doc_ids:
        if doc_id in all_chunks_by_doc:
            for chunk in all_chunks_by_doc[doc_id][:3]:
                fallback.append({
                    "text": chunk["text"],
                    "page": chunk["page"],
                    "doc_id": doc_id,
                    "score": 0.01,
                    "tfidf_score": 0.0,
                    "semantic_score": 0.0,
                })
    return fallback[:top_k]
