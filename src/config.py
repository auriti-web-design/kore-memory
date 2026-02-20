"""
Kore — Configurazione centralizzata
Tutte le variabili d'ambiente e costanti in un unico punto.
"""

import os
from pathlib import Path

# ── Percorsi ──────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = _PROJECT_ROOT / "data"

# Database
DEFAULT_DB_PATH = str(DATA_DIR / "memory.db")
DB_PATH = os.getenv("KORE_DB_PATH", DEFAULT_DB_PATH)

# API key
API_KEY_FILE = DATA_DIR / ".api_key"

# ── Server ────────────────────────────────────────────────────────────────────

HOST = os.getenv("KORE_HOST", "127.0.0.1")
PORT = int(os.getenv("KORE_PORT", "8765"))
LOCAL_ONLY = os.getenv("KORE_LOCAL_ONLY", "0") == "1"

# ── CORS ──────────────────────────────────────────────────────────────────────

CORS_ORIGINS = [o.strip() for o in os.getenv("KORE_CORS_ORIGINS", "").split(",") if o.strip()]

# ── Rate limiting ─────────────────────────────────────────────────────────────

RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/save": (30, 60),         # 30 req/min
    "/search": (60, 60),       # 60 req/min
    "/timeline": (60, 60),     # 60 req/min
    "/decay/run": (5, 3600),   # 5 req/ora
    "/compress": (2, 3600),    # 2 req/ora
}

# ── Embedder ──────────────────────────────────────────────────────────────────

EMBED_MODEL = os.getenv("KORE_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
MAX_EMBED_CHARS = int(os.getenv("KORE_MAX_EMBED_CHARS", "8000"))

# ── Compressor ────────────────────────────────────────────────────────────────

SIMILARITY_THRESHOLD = float(os.getenv("KORE_SIMILARITY_THRESHOLD", "0.88"))

# ── Versione ──────────────────────────────────────────────────────────────────

VERSION = "0.5.2"
