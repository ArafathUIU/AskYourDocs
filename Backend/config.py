import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
DOCS_DIR = STORAGE_DIR / "docs"
INDEXES_DIR = STORAGE_DIR / "indexes"
TEXTS_DIR = STORAGE_DIR / "texts"

# Create dirs if they don't exist
for d in [DOCS_DIR, INDEXES_DIR, TEXTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Or: "mixtral-8x7b-32768", "gemma2-9b-it"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K_CHUNKS = 6
MAX_TOKENS = 2048