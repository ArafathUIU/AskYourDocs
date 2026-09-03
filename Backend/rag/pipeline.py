from rag.retrieve import retrieve_chunks
from rag.llm import generate_answer
from rag.rerank import rerank_chunks
from rag.query_expander import expand_query
from config import TOP_K_CHUNKS


def process_pipeline_chunks(
    query: str,
    doc_ids: list[str],
    top_k: int = TOP_K_CHUNKS,
) -> tuple[list[dict], int]:
    """
    RAG pipeline steps 1 to 3: expand -> retrieve -> rerank.
    Returns (processed_chunks, queries_count).
    """
    # Step 1: Expand query into multiple variations
    try:
        queries = expand_query(query)
    except Exception:
        queries = [query]

    # Step 2: Retrieve for each query variation, deduplicate
    all_chunks = []
    seen = set()
    for q in queries:
        chunks = retrieve_chunks(q, doc_ids, top_k=top_k * 3)
        for c in chunks:
            key = c["text"][:120]
            if key not in seen:
                seen.add(key)
                all_chunks.append(c)

    if not all_chunks:
        return [], len(queries)

    # Step 3: Re-rank with cross-encoder
    if len(all_chunks) > 1:
        try:
            all_chunks = rerank_chunks(query, all_chunks, top_k=top_k * 2)
        except Exception:
            all_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
            all_chunks = all_chunks[:top_k * 2]

    return all_chunks[:top_k], len(queries)


def run_rag_pipeline(
    query: str,
    doc_ids: list[str],
    doc_names: dict[str, str],
    chat_history: list[dict] | None = None,
    top_k: int = TOP_K_CHUNKS,
    model: str | None = None,
) -> dict:
    """
    Full RAG pipeline: expand -> retrieve -> rerank -> generate.
    Returns {answer, sources, chunks_found}.
    """
    context_chunks, queries_count = process_pipeline_chunks(query, doc_ids, top_k=top_k)

    if not context_chunks:
        return {
            "answer": "I couldn't find relevant information in your documents to answer this question. Please try rephrasing or uploading additional documents.",
            "sources": [],
            "chunks_found": 0,
        }

    # Step 4: Generate answer
    result = generate_answer(
        query=query,
        context_chunks=context_chunks,
        doc_names=doc_names,
        chat_history=chat_history,
        model=model,
    )

    result["queries_used"] = queries_count
    result["chunks_found"] = len(context_chunks)
    return result


