import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent  # Backend's parent = project root
load_dotenv(PROJECT_ROOT / ".env")

# Auto-detect: Vercel uses /tmp, local uses Backend directory
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
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "")

# Auto-detect endpoint: OpenAI keys (sk-proj-*) use OpenAI, rest use OpenCode Go
if OPENCODE_API_KEY.startswith("sk-proj-"):
    OPENCODE_BASE_URL = "https://api.openai.com/v1"
    LLM_MODEL = "gpt-4o-mini"
else:
    OPENCODE_BASE_URL = "https://opencode.ai/zen/go/v1"
    LLM_MODEL = "deepseek-v4-pro"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K_CHUNKS = 6
MAX_TOKENS = 2048
