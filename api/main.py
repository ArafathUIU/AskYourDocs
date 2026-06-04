import sys
from pathlib import Path

# Add Backend to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Backend"))

from main import app