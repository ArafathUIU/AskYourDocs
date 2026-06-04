from rag.retrieve import retrieve_chunks
from rag.llm import generate_answer
from rag.rerank import rerank_chunks
from config import TOP_K_CHUNKS


def run_rag_pipeline(
    query: str,
    doc_ids: list[str],
    doc_names: dict[str, str],
    chat_history: list[dict] | None = None,
    top_k: int = TOP_K_CHUNKS,
) -> dict:
    """
    Full RAG pipeline: retrieve -> rerank -> generate.
    Returns {answer, sources, chunks_found}.
    """
    # Step 1: Retrieve more candidates (3x top_k for re-ranking)
    chunks = retrieve_chunks(query, doc_ids, top_k=top_k * 3)

    # Step 2: Re-rank with cross-encoder
    if len(chunks) > top_k:
        try:
            chunks = rerank_chunks(query, chunks, top_k=top_k)
        except Exception:
            chunks = chunks[:top_k]

    # Step 3: Generate answer
    result = generate_answer(
        query=query,
        context_chunks=chunks,
        doc_names=doc_names,
        chat_history=chat_history,
    )

    result["chunks_found"] = len(chunks)
    return result
