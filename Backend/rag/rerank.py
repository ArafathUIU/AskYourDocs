from sentence_transformers import CrossEncoder

RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL_NAME)
    return _reranker


def rerank_chunks(query: str, chunks: list[dict], top_k: int = 6) -> list[dict]:
    if not chunks:
        return []
    if len(chunks) <= top_k:
        return chunks

    reranker = get_reranker()
    pairs = [[query, c["text"]] for c in chunks]
    scores = reranker.predict(pairs, show_progress_bar=False)

    for i, score in enumerate(scores):
        chunks[i]["rerank_score"] = float(score)

    chunks.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return chunks[:top_k]
