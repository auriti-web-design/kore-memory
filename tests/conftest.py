import os
import sqlite3
import tempfile

# Shared temp DB for all tests — set BEFORE any kore_memory import
_TEST_DB = tempfile.mktemp(suffix=".db")
os.environ["KORE_DB_PATH"] = _TEST_DB
os.environ["KORE_LOCAL_ONLY"] = "1"
os.environ["KORE_TEST_MODE"] = "1"

import pytest  # noqa: E402

from kore_memory.database import init_db  # noqa: E402
from kore_memory.main import _rate_buckets  # noqa: E402

# Initialize schema once
init_db()

# Verify tables were created (fail fast if something went wrong)
_verify_conn = sqlite3.connect(_TEST_DB)
_tables = {r[0] for r in _verify_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
_verify_conn.close()
assert "memories" in _tables, f"init_db() did not create memories table in {_TEST_DB}. Found: {_tables}"


@pytest.fixture(autouse=True, scope="session")
def _ensure_db():
    """Session-scoped fixture: ensure DB is initialized and env var is set."""
    # Re-verify at session start (after all conftest modules are loaded)
    assert os.environ.get("KORE_DB_PATH") == _TEST_DB, (
        f"KORE_DB_PATH changed! Expected {_TEST_DB}, got {os.environ.get('KORE_DB_PATH')}"
    )
    conn = sqlite3.connect(_TEST_DB)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "memories" in tables, f"memories table missing at session start. DB: {_TEST_DB}, tables: {tables}"
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter state between tests."""
    _rate_buckets.clear()
    yield
    _rate_buckets.clear()
