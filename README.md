<div align="center">

<img src="assets/logo.svg" alt="Kore Memory" width="420"/>

<br/>

**The memory layer that thinks like a human.**
<br/>
Remembers what matters. Forgets what doesn't. Never calls home.

<br/>

[![CI](https://github.com/auriti-web-design/kore-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/auriti-web-design/kore-memory/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/kore-memory.svg?style=flat-square&color=7c3aed)](https://pypi.org/project/kore-memory/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Zero Cloud](https://img.shields.io/badge/cloud-zero-orange?style=flat-square)]()
[![Multilingual](https://img.shields.io/badge/languages-50%2B-purple?style=flat-square)]()

<br/>

[**Install**](#-install) · [**Quickstart**](#-quickstart) · [**How it works**](#-how-it-works) · [**API**](#-api-reference) · [**Changelog**](CHANGELOG.md) · [**Roadmap**](#-roadmap)

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
| Tags & Relations (graph) | ✅ | ❌ | ✅ | ❌ |
| TTL / Auto-expiration | ✅ | ❌ | ❌ | ❌ |
| MCP Server (Claude, Cursor) | ✅ | ❌ | ❌ | ❌ |
| Batch API | ✅ | ❌ | ❌ | ❌ |
| Export / Import (JSON) | ✅ | ❌ | ✅ | ❌ |
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

### 🏷️ Tags & Relations
Organize memories with tags and build a knowledge graph by linking related memories together. Search by tag, traverse relations bidirectionally.

### ⏳ TTL — Time-to-Live
Set an expiration on any memory. Expired memories are automatically excluded from search, export, and timeline. Run `/cleanup` to purge them, or let the decay pass handle it.

### 📦 Batch API
Save up to 100 memories in a single request. Perfect for bulk imports and agent bootstrapping.

### 💾 Export / Import
Full JSON export of all active memories. Import from a previous backup or migrate between instances.

### 🔌 MCP Server (Model Context Protocol)
Native integration with Claude, Cursor, and any MCP-compatible client. Exposes save, search, timeline, decay, compress, and export as MCP tools.

### 🔐 Agent Namespace Isolation
Multi-agent safe. Each agent sees only its own memories, even on a shared server.

---

## 📦 Install

```bash
# Core (FTS5 search only)
pip install kore-memory

# With semantic search (50+ languages, local embeddings)
pip install kore-memory[semantic]

# With MCP server (Claude, Cursor integration)
pip install kore-memory[semantic,mcp]
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
# Save with TTL (auto-expires after 48 hours)
curl -X POST http://localhost:8765/save \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: my-agent" \
  -d '{"content": "Deploy scheduled for Friday", "category": "task", "ttl_hours": 48}'
```

```bash
# Batch save (up to 100 per request)
curl -X POST http://localhost:8765/save/batch \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: my-agent" \
  -d '{"memories": [
    {"content": "React 19 supports server components", "category": "project"},
    {"content": "Always use parameterized queries", "category": "decision", "importance": 5}
  ]}'
```

```bash
# Tag a memory
curl -X POST http://localhost:8765/memories/1/tags \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: my-agent" \
  -d '{"tags": ["react", "frontend"]}'

# Search by tag
curl "http://localhost:8765/tags/react/memories" \
  -H "X-Agent-Id: my-agent"
```

```bash
# Link two related memories
curl -X POST http://localhost:8765/memories/1/relations \
  -H "Content-Type: application/json" \
  -H "X-Agent-Id: my-agent" \
  -d '{"target_id": 2, "relation": "depends_on"}'
```

```bash
# Timeline for a subject
curl "http://localhost:8765/timeline?subject=project+alpha" \
  -H "X-Agent-Id: my-agent"

# Run daily decay pass (cron this)
curl -X POST http://localhost:8765/decay/run \
  -H "X-Agent-Id: my-agent"

# Compress similar memories
curl -X POST http://localhost:8765/compress \
  -H "X-Agent-Id: my-agent"

# Export all memories (JSON backup)
curl "http://localhost:8765/export" \
  -H "X-Agent-Id: my-agent" > backup.json

# Cleanup expired memories
curl -X POST http://localhost:8765/cleanup \
  -H "X-Agent-Id: my-agent"
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

### Core

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/save` | Save a memory (auto-scored). Supports `ttl_hours` for auto-expiration |
| `POST` | `/save/batch` | Save up to 100 memories in one request |
| `GET` | `/search?q=...` | Semantic search with pagination (`limit`, `offset`) |
| `GET` | `/timeline?subject=...` | Chronological history with pagination |
| `DELETE` | `/memories/{id}` | Delete a memory |

### Tags

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/memories/{id}/tags` | Add tags to a memory |
| `DELETE` | `/memories/{id}/tags` | Remove tags from a memory |
| `GET` | `/memories/{id}/tags` | List tags for a memory |
| `GET` | `/tags/{tag}/memories` | Search memories by tag |

### Relations

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/memories/{id}/relations` | Create a relation to another memory |
| `GET` | `/memories/{id}/relations` | List all relations (bidirectional) |

### Maintenance

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/decay/run` | Recalculate decay scores + cleanup expired |
| `POST` | `/compress` | Merge similar memories |
| `POST` | `/cleanup` | Remove expired memories (TTL) |

### Backup

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/export` | Export all active memories (JSON) |
| `POST` | `/import` | Import memories from a previous export |

### Utility

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check + capabilities |

Interactive docs: **http://localhost:8765/docs**

### Headers

| Header | Required | Description |
|---|:---:|---|
| `X-Agent-Id` | No | Agent namespace (default: `"default"`) |
| `X-Kore-Key` | On non-localhost | API key (auto-generated on first run) |

### Categories

`general` · `project` · `trading` · `finance` · `person` · `preference` · `task` · `decision`

### Save Request Body

```json
{
  "content": "Memory content (3–4000 chars)",
  "category": "general",
  "importance": 1,
  "ttl_hours": null
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `content` | string | *required* | Memory text (3–4000 chars) |
| `category` | string | `"general"` | One of the categories above |
| `importance` | int (1–5) | `1` | 1 = auto-scored, 2–5 = explicit |
| `ttl_hours` | int \| null | `null` | Auto-expire after N hours (1–8760). Null = never expires |

---

## ⚙️ Configuration

| Env Var | Default | Description |
|---|---|---|
| `KORE_DB_PATH` | `data/memory.db` | Custom database path |
| `KORE_HOST` | `127.0.0.1` | Server bind address |
| `KORE_PORT` | `8765` | Server port |
| `KORE_LOCAL_ONLY` | `0` | Skip auth for localhost requests |
| `KORE_API_KEY` | auto-generated | Override API key |
| `KORE_CORS_ORIGINS` | *(empty)* | Comma-separated allowed origins |
| `KORE_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Sentence-transformers model |
| `KORE_MAX_EMBED_CHARS` | `8000` | Max chars sent to embedder (OOM protection) |
| `KORE_SIMILARITY_THRESHOLD` | `0.88` | Cosine threshold for compression |

---

## 🔌 MCP Server

Kore ships with a native [Model Context Protocol](https://modelcontextprotocol.io) server for direct integration with Claude, Cursor, and any MCP-compatible client.

```bash
# Install with MCP support
pip install kore-memory[mcp]

# Run the MCP server (stdio transport, default)
kore-mcp
```

### Available MCP Tools

| Tool | Description |
|---|---|
| `memory_save` | Save a memory with auto-scoring |
| `memory_search` | Semantic or full-text search |
| `memory_timeline` | Chronological history for a subject |
| `memory_decay_run` | Recalculate decay scores |
| `memory_compress` | Merge similar memories |
| `memory_export` | Export all active memories |

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kore-memory": {
      "command": "kore-mcp",
      "args": []
    }
  }
}
```

### Cursor / Claude Code Configuration

Add to your `.claude/settings.json` or MCP config:

```json
{
  "mcpServers": {
    "kore-memory": {
      "command": "kore-mcp"
    }
  }
}
```

---

## 🔐 Security

- **API key** — auto-generated on first run, saved as `data/.api_key` (chmod 600)
- **Agent isolation** — agents can only read/write/delete their own memories
- **SQL injection proof** — parameterized queries throughout
- **Timing-safe key comparison** — `secrets.compare_digest`
- **Input validation** — Pydantic v2 on all endpoints
- **Rate limiting** — per IP + path, configurable limits
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `CSP`, `Referrer-Policy`
- **CORS** — restricted by default, configurable via `KORE_CORS_ORIGINS`
- **FTS5 sanitization** — special characters stripped, token count limited
- **OOM protection** — embedding input capped at 8000 chars

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
- [x] Rate limiting
- [x] Security headers & CORS
- [x] Export / Import (JSON)
- [x] Tags & Relations (knowledge graph)
- [x] Batch API
- [x] TTL / Auto-expiration
- [x] MCP Server (Claude, Cursor)
- [x] Pagination (offset + has_more)
- [x] Centralized config (env vars)
- [x] OOM protection (embedder)
- [x] Vector index cache
- [ ] npm / Python client SDK
- [ ] Web dashboard (localhost UI)
- [ ] PostgreSQL backend
- [ ] Embeddings v2 (multilingual-e5-large)

---

## 🤝 Built with OpenClaw

Kore was developed and is actively used inside **[OpenClaw](https://openclaw.ai)** — a personal AI agent platform that runs Claude on your own infrastructure.

OpenClaw uses Kore as its persistent memory layer: every important conversation, decision, and preference gets stored, scored, and retrieved semantically across sessions.

If you're building AI agents with OpenClaw, Kore integrates natively — just point your skill at `http://localhost:8765`.

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
<br/>
<sub>Developed and battle-tested with <a href="https://openclaw.ai">OpenClaw</a> — the personal AI agent platform.</sub>
</div>
