# Kore Memory

> **The memory layer that thinks like a human: remembers what matters, forgets what doesn't, and never calls home.**

[![PyPI version](https://img.shields.io/pypi/v/kore-memory.svg)](https://pypi.org/project/kore-memory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Zero Cloud Dependencies](https://img.shields.io/badge/cloud-zero-green.svg)]()

---

## Why Kore?

Every AI agent memory tool out there has the same problem: they remember everything forever, require cloud APIs, or need an LLM just to decide what's worth storing.

**Kore is different.**

| Feature | Kore | Mem0 | Letta | Memori |
|---|---|---|---|---|
| Runs fully offline | ✅ | ❌ | ❌ | ❌ |
| No LLM required | ✅ | ❌ | ❌ | ✅ |
| Memory Decay (Ebbinghaus) | ✅ | ❌ | ❌ | ❌ |
| Auto-importance scoring | ✅ local | ✅ via LLM | ❌ | ❌ |
| Memory Compression | ✅ | ❌ | ❌ | ❌ |
| Semantic search (50+ langs) | ✅ local | ✅ via API | ✅ | ✅ |
| Timeline API | ✅ | ❌ | ❌ | ❌ |
| Access reinforcement | ✅ | ❌ | ❌ | ❌ |
| Install in 2 minutes | ✅ | ❌ | ❌ | ❌ |

---

## How It Works

Kore models memory the way the human brain does:

1. **Save** — store a memory with optional category and importance
2. **Auto-score** — Kore calculates importance locally using content analysis (no API calls)
3. **Decay** — memories fade over time using the [Ebbinghaus forgetting curve](https://en.wikipedia.org/wiki/Forgetting_curve)
4. **Reinforce** — retrieving a memory resets its clock and boosts its score
5. **Compress** — similar memories are automatically merged to keep the DB lean
6. **Search** — semantic search in any language, filtered by relevance and freshness

---

## Quickstart

```bash
pip install kore-memory
pip install kore-memory[semantic]   # + multilingual embeddings (50+ languages)

kore                                # starts server on http://localhost:8765
```

### Save a memory

```bash
curl -X POST http://localhost:8765/save \
  -H "Content-Type: application/json" \
  -d '{"content": "User prefers concise responses", "category": "preference"}'
# → {"id": 1, "importance": 4, "message": "Memory saved"}
# importance was auto-scored: "preference" category + keyword "prefers" → 4
```

### Search (any language)

```bash
# English query finds Italian content, French content, etc.
curl "http://localhost:8765/search?q=user+preferences&limit=5"
```

### Run decay pass (call daily via cron)

```bash
curl -X POST http://localhost:8765/decay/run
# → {"updated": 42, "message": "Decay pass complete"}
```

### Compress similar memories

```bash
curl -X POST http://localhost:8765/compress
# → {"clusters_found": 3, "memories_merged": 7, "new_records_created": 3}
```

### Timeline: what did I know about X over time?

```bash
curl "http://localhost:8765/timeline?subject=project+alpha"
```

---

## Memory Decay

Kore uses the **Ebbinghaus forgetting curve** to assign each memory a `decay_score` between 0.0 and 1.0:

```
decay = e^(-t * ln(2) / half_life)
```

Where:
- `t` = days since last access
- `half_life` = base days before 50% decay, adjusted by importance level

| Importance | Half-life | Meaning |
|---|---|---|
| 1 (low) | 7 days | Casual notes |
| 2 (normal) | 14 days | General context |
| 3 (important) | 30 days | Project info |
| 4 (high) | 90 days | Critical decisions |
| 5 (critical) | 365 days | Passwords, rules, never forget |

Every time a memory is retrieved, its `access_count` increases and its half-life is extended by 15% — just like spaced repetition in human learning.

---

## Auto-Importance Scoring

When you save a memory without an explicit importance level, Kore scores it automatically:

- **Category baseline** — `preference` starts at 4, `finance` at 3, `general` at 1
- **Keyword signals** — words like `password`, `token`, `urgente` → importance 5
- **Content length** — detailed content gets a small boost

Zero LLM calls. Zero API costs.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/save` | Save a memory |
| `GET` | `/search` | Semantic search (any language) |
| `GET` | `/timeline` | Chronological history for a subject |
| `DELETE` | `/memories/{id}` | Delete a memory |
| `POST` | `/decay/run` | Update all decay scores |
| `POST` | `/compress` | Merge similar memories |
| `GET` | `/health` | Health check + capabilities |

Full interactive docs: `http://localhost:8765/docs`

---

## Categories

`general` · `project` · `trading` · `finance` · `person` · `preference` · `task` · `decision`

---

## Requirements

- Python 3.11+
- SQLite (built into Python)
- Optional: `sentence-transformers` for semantic search

No PostgreSQL. No Redis. No Docker. No API keys.

---

## License

MIT — use it, fork it, build on it.

---

*Built with ❤️ for AI agents that deserve better memory.*
