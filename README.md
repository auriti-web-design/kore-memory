<div align="center">

<img src="assets/logo.svg" alt="Kore Memory" width="420"/>

<br/>

**The memory layer that thinks like a human.**
<br/>
Remembers what matters. Forgets what doesn't. Never calls home.

<br/>

[![PyPI version](https://img.shields.io/pypi/v/kore-memory.svg?style=flat-square&color=7c3aed)](https://pypi.org/project/kore-memory/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-17%20passing-brightgreen?style=flat-square)]()
[![Zero Cloud](https://img.shields.io/badge/cloud-zero-orange?style=flat-square)]()
[![Multilingual](https://img.shields.io/badge/languages-50%2B-purple?style=flat-square)]()

<br/>

[**Install**](#-install) · [**Quickstart**](#-quickstart) · [**How it works**](#-how-it-works) · [**API**](#-api-reference) · [**Roadmap**](#-roadmap)

</div>

---

## Why Kore?

Every AI agent memory tool has the same flaw: they remember everything forever, phone home to cloud APIs, or need an LLM just to decide what's worth storing.

**Kore is different.**

<div align="center">

| Feature | **Kore** | Mem0 | Letta | Memori |
|---|:---:|:---:|:---:|:---:|
| Runs fully offline | ✅ | ❌ | ❌ | ❌ |
| No LLM required | ✅ | ❌ | ❌ | ✅ |
| **Memory Decay** (Ebbinghaus) | ✅ | ❌ | ❌ | ❌ |
| Auto-importance scoring | ✅ local | ✅ via LLM | ❌ | ❌ |
| **Memory Compression** | ✅ | ❌ | ❌ | ❌ |
| Semantic search (50+ langs) | ✅ local | ✅ via API | ✅ | ✅ |
| Timeline API | ✅ | ❌ | ❌ | ❌ |
| Agent namespace isolation | ✅ | ✅ | ✅ | ❌ |
| Install in 2 minutes | ✅ | ❌ | ❌ | ❌ |

</div>

---

## ✨ Key Features

### 📉 Memory Decay — The Ebbinghaus Engine
Memories fade over time using the [Ebbinghaus forgetting curve](https://en.wikipedia.org/wiki/Forgetting_curve). Critical memories persist for months. Casual notes fade in days.

```
decay = e^(-t · ln2 / half_life)
```

Every retrieval resets the clock and boosts the decay score — just like spaced repetition in human learning.

### 🤖 Auto-Importance Scoring
No LLM call needed. Kore scores importance locally using content analysis — keywords, category, length.

```python
"API token: sk-abc123"  →  importance: 5  (critical, never forget)
"Juan prefers dark mode"  →  importance: 4  (preference)
"Meeting at 3pm"  →  importance: 2  (general)
```

### 🔍 Semantic Search in 50+ Languages
Powered by local `sentence-transformers`. Find memories by meaning, not just keywords. Search in English, get results in Italian. Zero API calls.

### 🗜️ Memory Compression
Similar memories (cosine similarity > 0.88) are automatically merged into richer, deduplicated records. Your DB stays lean forever.

### 📅 Timeline API
"What did I know about project X last month?" — trace any subject chronologically.

### 🔐 Agent Namespace Isolation
Multi-agent safe. Each agent sees only its own memories, even on a shared server.

---

## 📦 Install

```bash
# Core (FTS5 search only)
pip install kore-memory

# With semantic search (50+ languages, local embeddings)
pip install kore-memory[semantic]
```

---

## 🚀 Quickstart

```bash
# Start the server
kore
# → Kore running on http://localhost:8765
```

```bash
# Save a memory
curl -X POST http://localhost:8765/save \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: my-agent" \
  -d '{"content": "User prefers concise responses in Italian", "category": "preference"}'

# → {"id": 1, "importance": 4, "message": "Memory saved"}
#   (importance auto-scored: preference category + keyword "prefers")
```

```bash
# Search — any language
curl "http://localhost:8765/search?q=user+preferences&limit=5" \
  -H "X-Agent-Id: my-agent"
```

```bash
# Run daily decay pass (cron this)
curl -X POST http://localhost:8765/decay/run

# Compress similar memories
curl -X POST http://localhost:8765/compress

# Timeline for a subject
curl "http://localhost:8765/timeline?subject=project+alpha"
```

---

## 🧠 How It Works

```
Save memory
    │
    ▼
Auto-score importance (1–5)
    │
    ▼
Generate embedding (local, offline)
    │
    ▼
Store in SQLite with decay_score = 1.0
    │
    │   [time passes]
    │
    ▼
decay_score decreases (Ebbinghaus curve)
    │
    ▼
Search query arrives
    │
    ▼
Semantic similarity scored
    │
    ▼
Filter out forgotten memories (decay < 0.05)
    │
    ▼
Re-rank by effective_score = similarity × decay × importance
    │
    ▼
Access reinforcement: decay_score += 0.05
    │
    ▼
Return top-k results
```

### Memory Half-Lives

| Importance | Label | Half-life |
|:---:|:---:|:---:|
| 1 | Low | 7 days |
| 2 | Normal | 14 days |
| 3 | Important | 30 days |
| 4 | High | 90 days |
| 5 | Critical | 365 days |

Each retrieval extends the half-life by **+15%** (spaced repetition effect).

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/save` | Save a memory (auto-scored) |
| `GET` | `/search?q=...` | Semantic search (any language) |
| `GET` | `/timeline?subject=...` | Chronological history |
| `DELETE` | `/memories/{id}` | Delete a memory |
| `POST` | `/decay/run` | Update all decay scores |
| `POST` | `/compress` | Merge similar memories |
| `GET` | `/health` | Health check + capabilities |

Interactive docs: **http://localhost:8765/docs**

### Headers

| Header | Required | Description |
|---|:---:|---|
| `X-Agent-Id` | No | Agent namespace (default: `"default"`) |
| `X-Kore-Key` | On non-localhost | API key (auto-generated on first run) |

### Categories

`general` · `project` · `trading` · `finance` · `person` · `preference` · `task` · `decision`

---

## ⚙️ Configuration

| Env Var | Default | Description |
|---|---|---|
| `KORE_API_KEY` | auto-generated | Override API key |
| `KORE_LOCAL_ONLY` | `1` | Skip auth for localhost requests |
| `KORE_DB_PATH` | `data/memory.db` | Custom DB path |

---

## 🔐 Security

- **API key** — auto-generated on first run, saved as `data/.api_key` (chmod 600)
- **Agent isolation** — agents can only read/write/delete their own memories
- **SQL injection proof** — parameterized queries throughout
- **Timing-safe key comparison** — `secrets.compare_digest`
- **Input validation** — Pydantic v2 on all endpoints

---

## 🗺️ Roadmap

- [x] FTS5 full-text search
- [x] Semantic search (multilingual)
- [x] Memory Decay (Ebbinghaus)
- [x] Auto-importance scoring
- [x] Memory Compression
- [x] Timeline API
- [x] Agent namespace isolation
- [x] API key authentication
- [ ] Rate limiting
- [ ] npm client SDK
- [ ] Web dashboard (localhost UI)
- [ ] Export / Import (JSON)
- [ ] Embeddings v2 (multilingual-e5-large)

---

## 🛠️ Development

```bash
git clone https://github.com/auriti-web-design/kore-memory
cd kore-memory
python -m venv .venv && source .venv/bin/activate
pip install -e ".[semantic,dev]"
pytest tests/ -v
```

---

## 📄 License

MIT © [Juan Auriti](https://github.com/auriti-web-design)

---

<div align="center">
<sub>Built for AI agents that deserve better memory.</sub>
</div>
