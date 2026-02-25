import os
import tempfile

# Shared temp DB for all tests — set BEFORE any kore_memory import
_TEST_DB = tempfile.mktemp(suffix=".db")
os.environ["KORE_DB_PATH"] = _TEST_DB
os.environ["KORE_LOCAL_ONLY"] = "1"
os.environ["KORE_TEST_MODE"] = "1"

import pytest

from kore_memory.database import init_db  # noqa: E402
from kore_memory.main import _rate_buckets  # noqa: E402

# Initialize schema once
init_db()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter state between tests."""
    _rate_buckets.clear()
    yield
    _rate_buckets.clear()
