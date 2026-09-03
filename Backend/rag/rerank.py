from config import ENABLE_ML

RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker = None
_reranker_error = None


def get_reranker():
    global _reranker, _reranker_error
    if not ENABLE_ML:
        raise RuntimeError("Re-ranking disabled in low-memory mode")
    if _reranker is None and _reranker_error is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(RERANK_MODEL_NAME)
        except Exception as e:
            _reranker_error = str(e)
    if _reranker_error:
        raise RuntimeError(f"Re-ranker unavailable: {_reranker_error}")
    return _reranker


def rerank_chunks(query: str, chunks: list[dict], top_k: int = 6) -> list[dict]:
    if not chunks:
        return []
    if len(chunks) == 1:
        return chunks


    try:
        reranker = get_reranker()
        pairs = [[query, c["text"]] for c in chunks]
        scores = reranker.predict(pairs, show_progress_bar=False)
        for i, score in enumerate(scores):
            chunks[i]["rerank_score"] = float(score)
        chunks.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    except Exception:
        pass  # Fallback to original order (already sorted by retrieval score)

    return chunks[:top_k]
