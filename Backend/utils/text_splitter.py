import re


def clean_text(text: str) -> str:
    """Clean common PDF extraction artifacts, orphan hyphenation, and excessive whitespace."""
    # Fix hyphenation across line breaks (e.g., 're- \nsearch' -> 'research')
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    # Normalize multiple whitespace characters
    text = re.sub(r'[ \t]+', ' ', text)
    # Normalize excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """Split text into sentences while respecting common punctuation and boundaries."""
    # Match sentence endings followed by whitespace and a capital letter/number
    sentence_endings = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'\(\[])')
    parts = sentence_endings.split(text)
    sentences = []
    for p in parts:
        p = p.strip()
        if p:
            sentences.append(p)
    return sentences or [text]


def split_into_chunks(text: str, chunk_size: int = 350, overlap: int = 60) -> list[dict]:
    """
    Advanced semantic & sentence-aware chunking strategy:
    1. Parses document page by page to strictly preserve authentic page numbers.
    2. Splits page text into coherent paragraphs and sentences.
    3. Builds chunks respecting sentence boundaries (no cutting mid-sentence).
    4. Applies sliding window overlap across sentence boundaries.
    5. Filters out noisy/empty fragments.
    """
    if not text or not text.strip():
        return []

    # Clean text
    cleaned_full_text = clean_text(text)

    # Split by page markers: [Page X]
    page_pattern = re.compile(r'\[Page\s+(\d+)\]', re.IGNORECASE)
    splits = page_pattern.split(cleaned_full_text)

    pages = []
    if len(splits) == 1:
        pages.append((1, splits[0].strip()))
    else:
        i = 0
        if splits[0].strip() and not splits[0].strip().isdigit():
            pages.append((1, splits[0].strip()))
            i = 1

        while i < len(splits):
            val = splits[i].strip()
            if val.isdigit():
                page_num = int(val)
                page_text = splits[i + 1].strip() if (i + 1 < len(splits)) else ""
                pages.append((page_num, page_text))
                i += 2
            else:
                if val:
                    pages.append((1, val))
                i += 1

    chunks = []
    chunk_index = 0

    for page_num, page_text in pages:
        if not page_text:
            continue

        # Split page into paragraphs
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', page_text) if p.strip()]
        if not paragraphs:
            paragraphs = [page_text]

        # Extract sentences per paragraph
        page_sentences = []
        for p in paragraphs:
            page_sentences.extend(split_sentences(p))

        if not page_sentences:
            continue

        current_chunk_sentences = []
        current_word_count = 0

        for sentence in page_sentences:
            words_in_sentence = len(sentence.split())

            # If adding this sentence exceeds chunk_size and we already have content
            if current_word_count + words_in_sentence > chunk_size and current_chunk_sentences:
                chunk_body = " ".join(current_chunk_sentences).strip()
                if len(chunk_body.split()) >= 20:
                    chunks.append({
                        "text": chunk_body,
                        "page": page_num,
                        "chunk_index": chunk_index,
                    })
                    chunk_index += 1

                # Overlap: keep trailing sentences that fit within overlap size
                overlap_sentences = []
                overlap_count = 0
                for s in reversed(current_chunk_sentences):
                    s_count = len(s.split())
                    if overlap_count + s_count <= overlap:
                        overlap_sentences.insert(0, s)
                        overlap_count += s_count
                    else:
                        break

                current_chunk_sentences = overlap_sentences
                current_word_count = overlap_count

            current_chunk_sentences.append(sentence)
            current_word_count += words_in_sentence

        # Append any remaining sentences for this page
        if current_chunk_sentences:
            chunk_body = " ".join(current_chunk_sentences).strip()
            if len(chunk_body.split()) >= 15 or not chunks:
                chunks.append({
                    "text": chunk_body,
                    "page": page_num,
                    "chunk_index": chunk_index,
                })
                chunk_index += 1

    return chunks