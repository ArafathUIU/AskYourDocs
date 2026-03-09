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

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-opus-4-5"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K_CHUNKS = 6
MAX_TOKENS = 2048