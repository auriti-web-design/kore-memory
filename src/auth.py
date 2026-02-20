"""
Kore — Authentication & Authorization
API key validation + agent namespace isolation.

Config via environment variables:
  KORE_API_KEY   — master key (required in non-local mode)
  KORE_LOCAL_ONLY — if "1", skip auth for 127.0.0.1 requests (default: "0")
"""

import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException, Request, status

_KEY_FILE = Path(__file__).parent.parent / "data" / ".api_key"

# ── Key management ────────────────────────────────────────────────────────────

def get_or_create_api_key() -> str:
    """
    Load API key from env or file. Generate and persist one if missing.
    Priority: KORE_API_KEY env → data/.api_key file → auto-generate
    """
    env_key = os.getenv("KORE_API_KEY")
    if env_key:
        return env_key

    if _KEY_FILE.exists():
        return _KEY_FILE.read_text().strip()

    # Auto-generate a secure key on first run
    new_key = secrets.token_urlsafe(32)
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_text(new_key)
    _KEY_FILE.chmod(0o600)  # owner read/write only
    print(f"\n🔑 Kore API key generated: {new_key}")
    print(f"   Saved to: {_KEY_FILE}")
    print(f"   Set KORE_API_KEY env var or use X-Kore-Key header.\n")
    return new_key


_API_KEY: str | None = None


def _loaded_key() -> str:
    global _API_KEY
    if _API_KEY is None:
        _API_KEY = get_or_create_api_key()
    return _API_KEY


def _is_local(request: Request) -> bool:
    client_host = request.client.host if request.client else ""
    # "testclient" is the FastAPI TestClient host — treat as local in tests
    return client_host in ("127.0.0.1", "::1", "localhost", "testclient")


def _local_only_mode() -> bool:
    mode = os.getenv("KORE_LOCAL_ONLY", "0") == "1"
    return mode


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def require_auth(
    request: Request,
    x_kore_key: str | None = Header(default=None, alias="X-Kore-Key"),
) -> str:
    """
    FastAPI dependency: validates API key.
    In local-only mode, skips auth for 127.0.0.1 requests.
    Returns the validated API key (or 'local' for unauthenticated local requests).
    """
    if _local_only_mode() and _is_local(request):
        return "local"

    if not x_kore_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Pass X-Kore-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(x_kore_key, _loaded_key()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return x_kore_key


async def get_agent_id(
    request: Request,
    x_agent_id: str | None = Header(default=None, alias="X-Agent-Id"),
) -> str:
    """
    FastAPI dependency: extracts agent namespace.
    Defaults to 'default' when not provided.
    Agent IDs are sanitized to alphanumeric + dash/underscore only.
    """
    agent_id = (x_agent_id or "default").strip()
    # Sanitize: only allow safe chars
    safe = "".join(c for c in agent_id if c.isalnum() or c in "-_")
    if not safe:
        safe = "default"
    return safe[:64]  # max 64 chars
