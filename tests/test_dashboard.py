"""
Test per la dashboard web di Kore.
Verifica che /dashboard risponda correttamente e che l'HTML contenga le sezioni attese.
"""

import httpx
import pytest

from src.database import init_db
from src.main import app


@pytest.fixture(autouse=True)
def _setup_db():
    """Inizializza il database prima di ogni test."""
    init_db()


@pytest.fixture()
async def client():
    """Client HTTP async per i test (ASGITransport richiede AsyncClient)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ── Test route dashboard ─────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_dashboard_returns_html(client):
    """GET /dashboard deve ritornare 200 con content-type text/html."""
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.anyio
async def test_dashboard_contains_all_sections(client):
    """L'HTML deve contenere tutte e 7 le sezioni (tab) della dashboard."""
    resp = await client.get("/dashboard")
    html = resp.text
    sections = [
        "page-overview",
        "page-memories",
        "page-tags",
        "page-relations",
        "page-timeline",
        "page-maintenance",
        "page-backup",
    ]
    for section in sections:
        assert section in html, f"Sezione {section} mancante dall'HTML"


@pytest.mark.anyio
async def test_dashboard_no_auth_required(client):
    """La dashboard non deve richiedere autenticazione (no X-Kore-Key)."""
    resp = await client.get("/dashboard")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_dashboard_has_relaxed_csp(client):
    """La dashboard deve avere CSP allargato (unsafe-inline) non quello restrittivo delle API."""
    resp = await client.get("/dashboard")
    csp = resp.headers.get("content-security-policy", "")
    assert "'unsafe-inline'" in csp
    assert "default-src 'none'" not in csp


@pytest.mark.anyio
async def test_api_keeps_strict_csp(client):
    """Le API devono mantenere il CSP restrittivo (default-src 'none')."""
    resp = await client.get("/health")
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp


@pytest.mark.anyio
async def test_dashboard_contains_kore_branding(client):
    """L'HTML deve contenere il branding Kore (titolo, logo)."""
    resp = await client.get("/dashboard")
    html = resp.text
    assert "Kore" in html
    assert "Memory Dashboard" in html


@pytest.mark.anyio
async def test_dashboard_contains_js_api_helpers(client):
    """L'HTML deve contenere le funzioni JS per chiamare le API."""
    resp = await client.get("/dashboard")
    html = resp.text
    assert "function api(" in html
    assert "function doSearch(" in html
    assert "function doSave(" in html
    assert "function doExport(" in html
