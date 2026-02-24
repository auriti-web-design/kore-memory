"""
Kore — Memory Decay Engine
Implements human-like forgetting: memories fade over time unless reinforced.

Formula inspired by Ebbinghaus forgetting curve:
  decay = importance_factor * e^(-t / half_life)

Where:
  t              = days since last access
  half_life      = base days before 50% decay (modulated by importance)
  importance_fac = 1.0 to 2.0 (higher importance = slower decay)
  access_count   = each retrieval resets the clock and boosts score
"""

import math
from datetime import UTC, datetime

# Half-life in days per importance level (higher importance = longer half-life)
HALF_LIFE: dict[int, float] = {
    1: 7.0,    # low — fades in ~1 week
    2: 14.0,   # normal — fades in ~2 weeks
    3: 30.0,   # important — fades in ~1 month
    4: 90.0,   # very important — fades in ~3 months
    5: 365.0,  # critical — fades in ~1 year
}

# Access reinforcement: each retrieval extends half-life by this factor
ACCESS_BOOST = 0.15  # +15% half-life per access


def compute_decay(
    importance: int,
    created_at: str,
    last_accessed: str | None,
    access_count: int,
) -> float:
    """
    Compute current decay score (0.0–1.0) for a memory.
    1.0 = perfectly fresh, 0.0 = completely faded.
    """
    reference_time = last_accessed or created_at
    try:
        ref_dt = datetime.fromisoformat(reference_time).replace(tzinfo=UTC)
    except ValueError:
        ref_dt = datetime.now(UTC)

    now = datetime.now(UTC)
    days_elapsed = max(0.0, (now - ref_dt).total_seconds() / 86400)

    base_half_life = HALF_LIFE.get(importance, 14.0)
    effective_half_life = base_half_life * (1 + ACCESS_BOOST * access_count)

    # Ebbinghaus formula: R = e^(-t/S) where S is stability (half-life)
    decay = math.exp(-days_elapsed * math.log(2) / effective_half_life)
    return round(min(1.0, max(0.0, decay)), 4)


def effective_score(decay_score: float, importance: int) -> float:
    """
    Combined relevance score used for ranking search results.
    Balances semantic similarity with memory freshness and importance.
    """
    importance_weight = importance / 5.0  # normalize to 0.2–1.0
    return round(decay_score * importance_weight, 4)


def should_forget(decay_score: float, threshold: float = 0.05) -> bool:
    """Returns True when a memory has faded below the forgetting threshold."""
    return decay_score < threshold
