import fitz  # PyMuPDF
from pathlib import Path


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract all text from a PDF file."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    full_text = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if text.strip():
            full_text.append(f"[Page {page_num}]\n{text.strip()}")

    doc.close()
    return "\n\n".join(full_text)


def get_pdf_metadata(pdf_path: str | Path) -> dict:
    """Extract basic metadata from PDF."""
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))
    meta = doc.metadata
    page_count = len(doc)
    doc.close()
    return {
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "page_count": page_count,
    }