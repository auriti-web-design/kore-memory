"""
Kore Memory — Entity Extraction integration.
Extracts named entities from memory content and stores them as tags.

Uses spaCy for NER when available, falls back to regex-based extraction.
Entities are stored as tags with `entity:type:value` format.

Usage:
    from kore_memory.integrations.entities import extract_entities, auto_tag_entities

    entities = extract_entities("Meeting with Juan at Google on 2024-01-15")
    # [{"type": "person", "value": "Juan"}, {"type": "org", "value": "Google"}, ...]

    auto_tag_entities(memory_id=1, content="...", agent_id="default")
"""

from __future__ import annotations

import re
from typing import Any

# ── spaCy lazy loading ────────────────────────────────────────────────────────

_spacy_nlp: Any = None
_spacy_checked: bool = False
_HAS_SPACY: bool = False

# Mapping from spaCy entity labels to our entity types
_SPACY_LABEL_MAP: dict[str, str] = {
    "PERSON": "person",
    "ORG": "org",
    "GPE": "location",
    "DATE": "date",
    "MONEY": "money",
    "PRODUCT": "product",
}


def _get_spacy_nlp() -> Any:
    """Lazy-load spaCy model on first use. Returns None if unavailable."""
    global _spacy_nlp, _spacy_checked, _HAS_SPACY

    if _spacy_checked:
        return _spacy_nlp

    _spacy_checked = True
    try:
        import spacy

        _HAS_SPACY = True
        try:
            _spacy_nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not downloaded — try other common models
            for model_name in ("en_core_web_md", "en_core_web_lg"):
                try:
                    _spacy_nlp = spacy.load(model_name)
                    break
                except OSError:
                    continue
    except ImportError:
        _HAS_SPACY = False
        _spacy_nlp = None

    return _spacy_nlp


def spacy_available() -> bool:
    """Check if spaCy is available and a model is loaded."""
    _get_spacy_nlp()
    return _spacy_nlp is not None


# ── Regex-based fallback extractors ──────────────────────────────────────────

# Email: standard RFC-ish pattern
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

# URL: http/https URLs
_URL_RE = re.compile(r"https?://[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")

# Date: common formats (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, Month DD YYYY, etc.)
_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"  # 2024-01-15
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"  # 01/15/2024 or 15/01/24
    r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s*\d{4}\b"  # January 15, 2024
    r"|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{4}\b",  # 15 January 2024
    re.IGNORECASE,
)

# Money: currency values ($100, EUR 50.00, 1,000.50 USD, etc.)
_MONEY_RE = re.compile(
    r"[$\u20ac\u00a3\u00a5]\s*[\d,]+(?:\.\d{1,2})?"  # $100, EUR50.00
    r"|[\d,]+(?:\.\d{1,2})?\s*(?:USD|EUR|GBP|JPY|CHF|BTC|ETH)\b"  # 100 USD
    r"|(?:USD|EUR|GBP|JPY|CHF)\s*[\d,]+(?:\.\d{1,2})?",  # USD 100
    re.IGNORECASE,
)


def _extract_regex(text: str) -> list[dict[str, str]]:
    """Extract entities using regex patterns (no external dependencies)."""
    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for match in _EMAIL_RE.finditer(text):
        val = match.group().lower()
        key = ("email", val)
        if key not in seen:
            seen.add(key)
            entities.append({"type": "email", "value": val})

    for match in _URL_RE.finditer(text):
        val = match.group().rstrip(".,;:")
        key = ("url", val.lower())
        if key not in seen:
            seen.add(key)
            entities.append({"type": "url", "value": val})

    for match in _DATE_RE.finditer(text):
        val = match.group().strip()
        key = ("date", val.lower())
        if key not in seen:
            seen.add(key)
            entities.append({"type": "date", "value": val})

    for match in _MONEY_RE.finditer(text):
        val = match.group().strip()
        key = ("money", val.lower())
        if key not in seen:
            seen.add(key)
            entities.append({"type": "money", "value": val})

    return entities


def _extract_spacy(text: str) -> list[dict[str, str]]:
    """Extract entities using spaCy NER."""
    nlp = _get_spacy_nlp()
    if nlp is None:
        return []

    doc = nlp(text[:10000])  # Limit text length for performance
    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for ent in doc.ents:
        entity_type = _SPACY_LABEL_MAP.get(ent.label_)
        if entity_type is None:
            continue
        val = ent.text.strip()
        if not val:
            continue
        key = (entity_type, val.lower())
        if key not in seen:
            seen.add(key)
            entities.append({"type": entity_type, "value": val})

    return entities


# ── Public API ────────────────────────────────────────────────────────────────


def extract_entities(text: str) -> list[dict[str, str]]:
    """
    Extract entities from text content.

    Uses spaCy NER when available (PERSON, ORG, GPE, DATE, MONEY, PRODUCT),
    falls back to regex extraction (email, url, date, money).

    Both methods are combined when spaCy is available — spaCy handles named
    entities while regex catches structured patterns (emails, URLs) that
    spaCy may miss.

    Args:
        text: The text to extract entities from.

    Returns:
        List of dicts with 'type' and 'value' keys.
        Example: [{"type": "person", "value": "Juan"}, ...]
    """
    if not text or not text.strip():
        return []

    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    # Always run regex extraction (catches emails, URLs, structured patterns)
    regex_entities = _extract_regex(text)
    for ent in regex_entities:
        key = (ent["type"], ent["value"].lower())
        if key not in seen:
            seen.add(key)
            entities.append(ent)

    # Add spaCy entities if available
    if spacy_available():
        spacy_entities = _extract_spacy(text)
        for ent in spacy_entities:
            key = (ent["type"], ent["value"].lower())
            if key not in seen:
                seen.add(key)
                entities.append(ent)

    return entities


def auto_tag_entities(memory_id: int, content: str, agent_id: str = "default") -> int:
    """
    Extract entities from content and save them as tags on the memory.

    Tags are stored in `entity:type:value` format, e.g.:
    - `entity:person:juan`
    - `entity:email:user@example.com`
    - `entity:url:https://example.com`

    Args:
        memory_id: The memory ID to tag.
        content: The text content to extract entities from.
        agent_id: The agent namespace.

    Returns:
        Number of entity tags added.
    """
    from ..repository import add_tags

    entities = extract_entities(content)
    if not entities:
        return 0

    tags = []
    for ent in entities:
        # Normalize value for tag: lowercase, limit length
        value = ent["value"].strip().lower()[:80]
        tag = f"entity:{ent['type']}:{value}"
        tags.append(tag)

    if not tags:
        return 0

    return add_tags(memory_id, tags, agent_id=agent_id)


def search_entities(
    agent_id: str,
    entity_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, str]]:
    """
    Search entity tags across all memories for an agent.

    Queries the memory_tags table for tags matching `entity:*` pattern,
    optionally filtered by entity type.

    Args:
        agent_id: The agent namespace to search within.
        entity_type: Optional filter by entity type (e.g., "person", "email").
        limit: Maximum number of results (default: 50).

    Returns:
        List of dicts with 'type', 'value', 'memory_id', and 'tag' keys.
    """
    from ..database import get_connection

    pattern = f"entity:{entity_type.lower()}:%" if entity_type else "entity:%"

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT mt.memory_id, mt.tag
            FROM memory_tags mt
            JOIN memories m ON mt.memory_id = m.id
            WHERE mt.tag LIKE ?
              AND m.agent_id = ?
              AND m.compressed_into IS NULL
              AND (m.expires_at IS NULL OR m.expires_at > datetime('now'))
            ORDER BY m.created_at DESC
            LIMIT ?
            """,
            (pattern, agent_id, limit),
        ).fetchall()

    results: list[dict[str, str]] = []
    for row in rows:
        tag = row["tag"]
        parts = tag.split(":", 2)
        if len(parts) == 3:
            results.append(
                {
                    "type": parts[1],
                    "value": parts[2],
                    "memory_id": row["memory_id"],
                    "tag": tag,
                }
            )

    return results
