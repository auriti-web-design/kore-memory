"""
Kore — Auto-Importance Scorer
Calculates memory importance (1–5) locally, without any LLM API call.

Scoring factors:
  1. Content length       — longer = more detailed = more important
  2. Keyword signals      — critical words bump importance up
  3. Category baseline    — some categories are inherently more important
  4. Uniqueness           — if similar memories exist with high importance, inherit it
"""

# Keywords that signal high importance
HIGH_IMPORTANCE_KEYWORDS = {
    5: [
        "password",
        "token",
        "chiave",
        "secret",
        "api key",
        "credenziali",
        "urgente",
        "critico",
        "never",
        "mai",
        "sempre",
        "always",
        "private key",
        "segreto",
    ],
    4: [
        "decisione",
        "decision",
        "importante",
        "important",
        "priorità",
        "priority",
        "deadline",
        "scadenza",
        "pagamento",
        "payment",
        "debito",
        "debt",
        "errore critico",
        "bug critico",
        "non fare",
        "do not",
        "regola",
    ],
    3: [
        "progetto",
        "project",
        "strategia",
        "strategy",
        "obiettivo",
        "goal",
        "configurazione",
        "config",
        "server",
        "deploy",
        "produzione",
    ],
    2: [
        "nota",
        "note",
        "reminder",
        "appunto",
        "considerare",
        "consider",
    ],
}

# Category importance baselines
CATEGORY_BASELINE: dict[str, int] = {
    "general": 1,
    "preference": 4,
    "decision": 4,
    "finance": 3,
    "trading": 3,
    "project": 3,
    "task": 2,
    "person": 2,
}


def auto_score(content: str, category: str) -> int:
    """
    Return an importance score (1–5) based on content analysis.
    Used when importance is not explicitly set.
    """
    score = CATEGORY_BASELINE.get(category, 2)
    content_lower = content.lower()

    # Keyword signals — take the highest match
    for level in sorted(HIGH_IMPORTANCE_KEYWORDS.keys(), reverse=True):
        for kw in HIGH_IMPORTANCE_KEYWORDS[level]:
            if kw in content_lower:
                score = max(score, level)
                break

    # Length bonus: contenuto dettagliato e' probabilmente piu' importante
    word_count = len(content.split())
    if word_count > 60:
        score = min(5, score + 1)

    return max(1, min(5, score))
