import os
import tempfile
import pytest

# Abilita "testclient" come host trusted per FastAPI TestClient
os.environ["KORE_TEST_MODE"] = "1"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter state between tests."""
    from kore_memory.main import _rate_buckets
    _rate_buckets.clear()
    yield
    _rate_buckets.clear()
