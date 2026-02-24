"""
Kore — Web Dashboard
Dashboard HTML loaded from templates/dashboard.html at import time.
Falls back to inline string if template file is missing.
Vanilla JS + CSS, zero dipendenze esterne.
"""

import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

# ── Template location ────────────────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_PATH = _TEMPLATE_DIR / "dashboard.html"

# ── Fallback HTML (shown only if template file is missing) ───────────────────

_FALLBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kore — Dashboard Unavailable</title>
<style>
body { font-family: system-ui, sans-serif; background: #0c0c1d; color: #c8cad8;
       display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.msg { text-align: center; max-width: 480px; }
h1 { color: #7c3aed; margin-bottom: 1rem; }
code { background: #1e1e48; padding: 2px 8px; border-radius: 4px; }
</style>
</head>
<body>
<div class="msg">
<h1>Kore</h1>
<p>Dashboard template file not found.</p>
<p>Expected at: <code>kore_memory/templates/dashboard.html</code></p>
<p>Please reinstall the package or restore the template file.</p>
</div>
<script>/* fallback — no functionality */</script>
</body>
</html>
"""

# ── Load template at import time (cached in module variable) ─────────────────


def _load_template() -> str:
    """Load dashboard HTML from the template file.

    Reads templates/dashboard.html at import time so the file is only read once.
    If the template file is missing (e.g. broken install), falls back to a
    minimal error page.
    """
    try:
        return _TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        _logger.warning(
            "Dashboard template not found at %s — serving fallback page",
            _TEMPLATE_PATH,
        )
        return _FALLBACK_HTML
    except OSError as exc:
        _logger.error("Failed to read dashboard template: %s", exc)
        return _FALLBACK_HTML


_DASHBOARD_HTML: str = _load_template()


def get_dashboard_html() -> str:
    """Ritorna l'HTML completo della dashboard."""
    return _DASHBOARD_HTML
