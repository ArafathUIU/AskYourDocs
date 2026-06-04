from openai import OpenAI
import os
from dotenv import load_dotenv
from config import OPENCODE_API_KEY, OPENCODE_BASE_URL, LLM_MODEL

load_dotenv()

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = OPENCODE_API_KEY or os.getenv("OPENCODE_API_KEY", "")
        _client = OpenAI(api_key=api_key, base_url=OPENCODE_BASE_URL)
    return _client


def generate_answer(
    query: str,
    context_chunks: list[dict],
    doc_names: dict[str, str],
    chat_history: list[dict] | None = None,
    stream: bool = False,
    model: str | None = None,
) -> dict:
    if not context_chunks:
        return {
            "answer": "I couldn't find relevant information in your documents to answer this question. Please try rephrasing or uploading additional documents.",
            "sources": [],
        }

    # Build context
    context_parts = []
    sources_used = []
    for i, chunk in enumerate(context_chunks):
        doc_name = doc_names.get(chunk["doc_id"], chunk["doc_id"])
        context_parts.append(
            f"[Source {i+1}: {doc_name}, Page {chunk['page']}]\n{chunk['text']}"
        )
        sources_used.append({
            "index": i + 1,
            "doc_name": doc_name,
            "page": chunk["page"],
            "doc_id": chunk["doc_id"],
        })

    context_str = "\n\n---\n\n".join(context_parts)

    system_prompt = """You are AskYourDocs, an expert AI assistant that answers questions based strictly on provided document excerpts.

Guidelines:
- Answer using ONLY the provided document sources
- Always cite sources using [Source N] notation inline
- If the context doesn't fully answer the question, say so clearly
- Be precise, structured, and helpful
- For multi-part questions, use numbered lists
- Mention page numbers when relevant
- If asked to summarize, provide a well-structured summary with key points"""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Add chat history
    if chat_history:
        for msg in chat_history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current question with context
    messages.append({
        "role": "user",
        "content": f"""Document excerpts:

{context_str}

---

Question: {query}

Please answer based on the document excerpts above. Cite sources inline using [Source N]."""
    })

    selected_model = model or LLM_MODEL
    client = _get_client()

    if stream:
        stream_response = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
            stream=True,
        )
        return {
            "stream": stream_response,
            "sources": sources_used,
        }

    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
        max_tokens=2048,
        temperature=0.3,
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": sources_used,
        "tokens_used": response.usage.total_tokens if response.usage else 0,
    }