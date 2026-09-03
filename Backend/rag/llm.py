from openai import OpenAI
import os
from dotenv import load_dotenv
from config import GROQ_API_KEY, GROQ_BASE_URL, LLM_MODEL

load_dotenv()

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        base_url = GROQ_BASE_URL or os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        _client = OpenAI(api_key=api_key or "gsk_placeholder", base_url=base_url)
    return _client



VALID_MODELS = {
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
    "groq/compound",
    "groq/compound-mini",
}


def resolve_model(model: str | None) -> str:
    """Resolve model name safely with fallback to default Groq model."""
    if model and model in VALID_MODELS:
        return model
    if LLM_MODEL in VALID_MODELS:
        return LLM_MODEL
    return "openai/gpt-oss-20b"


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

    # Context budgeting to protect against Groq TPM rate limits (8000 TPM on free tier)
    MAX_CONTEXT_CHARS = 7500
    current_chars = 0
    selected_chunks = []
    for chunk in context_chunks:
        chunk_len = len(chunk.get("text", ""))
        if current_chars + chunk_len > MAX_CONTEXT_CHARS and selected_chunks:
            break
        selected_chunks.append(chunk)
        current_chars += chunk_len

    # Build context
    context_parts = []
    sources_used = []
    for i, chunk in enumerate(selected_chunks):
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

    system_prompt = """You are AskYourDocs, an expert AI assistant that answers questions based on provided document excerpts.

Guidelines:
- Answer thoroughly, accurately, and clearly using the provided document sources
- Always cite sources using [Source N] or [Source N, Page P] notation inline
- If asked to summarize, provide a well-structured summary with key findings, methodology, and conclusions
- For complex questions, use bullet points or numbered lists
- If the excerpts only partially address the question, synthesize the available facts and state any limitations"""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Add chat history (capped to avoid TPM limits)
    if chat_history:
        for msg in chat_history[-4:]:
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

    selected_model = resolve_model(model)
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