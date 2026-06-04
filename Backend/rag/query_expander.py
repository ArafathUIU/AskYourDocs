import json
from rag.llm import _get_client
from config import LLM_MODEL


def expand_query(query: str, model: str | None = None) -> list[str]:
    """
    Generate 4 keyword-rich variations of the query for better retrieval.
    Returns list of expanded queries including the original.
    """
    client = _get_client()
    selected_model = model or LLM_MODEL

    prompt = f"""Rewrite the following question into 4 different search-friendly keyword phrases.
Each variation should use different synonyms and phrasing to maximize document retrieval.
Keep each variation short (under 15 words).
Return ONLY a JSON array of strings, no explanation.

Question: {query}

Output format: ["variation 1", "variation 2", "variation 3", "variation 4"]"""

    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )
        text = response.choices[0].message.content.strip()
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()

        variations = json.loads(text)
        if isinstance(variations, list) and len(variations) > 0:
            # Deduplicate and add original
            seen = {query.lower()}
            result = [query]
            for v in variations:
                if isinstance(v, str) and v.strip().lower() not in seen:
                    seen.add(v.strip().lower())
                    result.append(v.strip())
            return result[:5]
    except Exception:
        pass

    return [query]
