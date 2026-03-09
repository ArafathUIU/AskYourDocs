import re


def split_into_chunks(text: str, chunk_size: int = 800, overlap: int = 150) -> list[dict]:
    """
    Split text into overlapping chunks, preserving page markers.
    Returns list of {text, page_hint} dicts.
    """
    # Split by page markers first
    page_pattern = re.compile(r'\[Page (\d+)\]')
    segments = page_pattern.split(text)

    # Rebuild as (page_num, text) pairs
    pages = []
    i = 0
    current_page = 1
    while i < len(segments):
        seg = segments[i].strip()
        if seg.isdigit():
            current_page = int(seg)
            i += 1
            if i < len(segments):
                pages.append((current_page, segments[i].strip()))
                i += 1
        else:
            if seg:
                pages.append((current_page, seg))
            i += 1

    # Flatten to words with page tracking
    all_words = []
    for page_num, page_text in pages:
        words = page_text.split()
        all_words.extend([(w, page_num) for w in words])

    if not all_words:
        return []

    chunks = []
    start = 0
    while start < len(all_words):
        end = min(start + chunk_size, len(all_words))
        chunk_words = all_words[start:end]
        chunk_text = " ".join(w for w, _ in chunk_words)
        # Most common page in this chunk
        pages_in_chunk = [p for _, p in chunk_words]
        dominant_page = max(set(pages_in_chunk), key=pages_in_chunk.count)
        chunks.append({
            "text": chunk_text,
            "page": dominant_page,
            "chunk_index": len(chunks),
        })
        start += chunk_size - overlap

    return chunks