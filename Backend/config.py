import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent  # Backend's parent = project root
load_dotenv(PROJECT_ROOT / ".env")

# Auto-detect: Vercel, Render, and other cloud platforms use /tmp
# Local uses Backend directory
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    BASE_DIR = Path("/tmp")
else:
    BASE_DIR = Path(__file__).parent


STORAGE_DIR = BASE_DIR / "storage"
DOCS_DIR = STORAGE_DIR / "docs"
INDEXES_DIR = STORAGE_DIR / "indexes"
TEXTS_DIR = STORAGE_DIR / "texts"

for d in [DOCS_DIR, INDEXES_DIR, TEXTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# API key & provider
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENCODE_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")



CHUNK_SIZE = 350
CHUNK_OVERLAP = 60
TOP_K_CHUNKS = 4
MAX_TOKENS = 2048



# Default to instant, zero-latency TF-IDF search; enable heavy PyTorch/HF models only if ENABLE_ML=1
ENABLE_ML = os.getenv("ENABLE_ML", "0") == "1"

