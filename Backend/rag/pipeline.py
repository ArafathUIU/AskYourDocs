from rag.retrieve import retrieve_chunks
from rag.llm import generate_answer
from config import TOP_K_CHUNKS


def run_rag_pipeline(
    query: str,
    doc_ids: list[str],
    doc_names: dict[str, str],
    chat_history: list[dict] | None = None,
    top_k: int = TOP_K_CHUNKS,
) -> dict:
    """
    Full RAG pipeline: retrieve → generate.
    Returns {answer, sources, chunks_found}.
    """
    # Retrieve relevant chunks
    chunks = retrieve_chunks(query, doc_ids, top_k=top_k)

    # Generate answer
    result = generate_answer(
        query=query,
        context_chunks=chunks,
        doc_names=doc_names,
        chat_history=chat_history,
    )

    result["chunks_found"] = len(chunks)
    return result