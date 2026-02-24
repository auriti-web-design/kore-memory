# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kore Memory is a persistent memory layer for AI agents (Python 3.11+, FastAPI, SQLite). Runs fully offline — no LLM calls, no cloud APIs. Implements Ebbinghaus forgetting curve decay, local auto-importance scoring, semantic search via sentence-transformers, and memory compression.

Published on PyPI as `kore-memory` (v0.6.0). JS SDK on npm as `kore-memory-client` (v0.5.3). MIT license.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[semantic,dev]"

# Run server
kore                                    # localhost:8765
kore --port 9000 --reload               # dev mode
./start.sh                              # background (PID in logs/kore.pid)

# Tests (pytest, 3 file: test_api, test_client, test_dashboard)
pytest tests/ -v
pytest tests/test_api.py::TestSave -v           # singola classe
pytest tests/test_api.py::TestSave::test_save_basic -v  # singolo test

# JS SDK
cd sdk/js && npm install && npm run build   # build con tsup
cd sdk/js && npm test                       # test con vitest

# Build per PyPI
pip install build && python -m build
```

## Architecture

```
Request → FastAPI (main.py) → Auth (auth.py) → Pydantic (models.py) → Repository (repository.py) → SQLite (database.py)
                                                     ↕               ↕            ↕
                                               scorer.py      embedder.py    decay.py
                                                             vector_index.py  compressor.py
```

**Entry points:**
- `kore_memory/cli.py` → comando `kore`, avvia uvicorn su `kore_memory.main:app`
- `kore_memory/main.py` → FastAPI app con lifespan (init_db), tutti gli endpoint REST + dashboard
- `kore_memory/mcp_server.py` → comando `kore-mcp`, server MCP (stdio) per Claude/Cursor

**Moduli core (kore_memory/):**

| Modulo | Righe | Responsabilita |
|--------|-------|---------------|
| `dashboard.py` | ~1200 | HTML/CSS/JS inline servito su `/dashboard`, zero dipendenze frontend |
| `repository.py` | ~595 | Logica business: save, search (FTS5 + semantic), delete, decay, timeline, tags, relations, batch, TTL |
| `client.py` | ~510 | Python client SDK (sync `KoreClient` + async `AsyncKoreClient`) |
| `main.py` | ~450 | FastAPI app, endpoint REST, lifespan, rate limiting, security headers |
| `compressor.py` | ~166 | Merge memorie con cosine similarity > 0.88. Clustering greedy |
| `mcp_server.py` | ~164 | FastMCP server, espone 6 tool: memory_save, memory_search, memory_timeline, run_decay, memory_compress, memory_export |
| `vector_index.py` | ~120 | Cache e gestione indice vettoriale per embeddings |
| `models.py` | ~120 | Pydantic v2 schemas. Categorie: general, project, trading, finance, person, preference, task, decision |
| `database.py` | ~117 | SQLite WAL mode, schema `memories` + `memories_fts` (FTS5), tabelle tags/relations |
| `auth.py` | ~114 | API key auto-generata, timing-safe comparison, agent namespace isolation via `X-Agent-Id` |
| `scorer.py` | ~70 | Auto-scoring importance 1-5 senza LLM: keyword signals, category baseline, length bonus |
| `decay.py` | ~69 | Curva di Ebbinghaus: `decay = e^(-t·ln2/half_life)`. Half-life 7gg→365gg. +15% per retrieval |
| `embedder.py` | ~61 | Wrapper sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dim). Lazy-loaded |
| `config.py` | ~52 | Configurazione centralizzata da env vars (tutti i `KORE_*`) |

**JS/TS SDK (sdk/js/):**
- `src/client.ts` — classe `KoreClient`, 17 metodi async
- `src/types.ts` — interfacce TypeScript
- `src/errors.ts` — gerarchia errori (`KoreError` → `KoreValidationError` | `KoreAuthError` | ...)
- Build: tsup (ESM + CJS), test: vitest

**Database schema:**
- Tabella `memories`: `id`, `agent_id`, `content`, `category`, `importance` (1-5), `decay_score` (0.0-1.0), `access_count`, `embedding` (JSON blob), `compressed_into` (FK self-ref), `expires_at` (TTL)
- Virtual table `memories_fts` (FTS5) su content + category con trigger automatici
- Tabella `memory_tags`: many-to-many tags
- Tabella `memory_relations`: graph relazioni tra memorie
- Indici su: agent_id, decay_score, compressed, category, importance, created_at

**Search flow:**
1. Se semantic=True e embeddings disponibili → cosine similarity via vector_index (O(n))
2. Altrimenti → FTS5 con wildcard
3. Filtra memorie con `decay_score < 0.05` (dimenticate) e TTL scaduto
4. Re-rank per `effective_score = decay * importance`
5. Reinforcement: `access_count++`, `decay_score += 0.05`

## Test Structure

3 file in `tests/` — usa `TestClient` FastAPI (in-process, no network). Ogni test crea un DB temporaneo (`KORE_DB_PATH` env var), usa `KORE_LOCAL_ONLY=1` per skip auth, isola con `X-Agent-Id: test-agent`.

- `test_api.py` (~525 righe) — classi: TestHealth, TestSave, TestAuth, TestAgentIsolation, TestSearch, TestDecay, TestCompress, TestTimeline, TestDelete
- `test_client.py` (~398 righe) — test Python client SDK
- `test_dashboard.py` (~97 righe) — test route dashboard

Config pytest in `pyproject.toml` (`asyncio_mode = "auto"`). No conftest.py.

## CI/CD

- `.github/workflows/ci.yml` — push/PR su main, matrix Python 3.11+3.12, pytest
- `.github/workflows/publish.yml` — tag v*, build + publish PyPI (trusted OIDC)
- `.github/workflows/build-sdk.yml` — manual dispatch, build JS SDK

## Environment Variables

| Variabile | Default | Uso |
|-----------|---------|-----|
| `KORE_API_KEY` | auto-generata in `data/.api_key` | Override API key |
| `KORE_LOCAL_ONLY` | `"0"` | Skip auth per localhost (`"1"` nei test) |
| `KORE_DB_PATH` | `data/memory.db` | Path DB (usato nei test per temp DB) |
| `KORE_HOST` | `127.0.0.1` | Bind address |
| `KORE_PORT` | `8765` | Server port |
| `KORE_CORS_ORIGINS` | *(vuoto)* | Allowed origins (comma-separated) |
| `KORE_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Modello sentence-transformers |
| `KORE_MAX_EMBED_CHARS` | `8000` | Max chars per embedder (OOM protection) |
| `KORE_SIMILARITY_THRESHOLD` | `0.88` | Soglia cosine per compression |

## Key Patterns

- **Agent isolation**: tutte le query DB filtrano per `agent_id`. Header `X-Agent-Id`, default `"default"`, sanitizzato a `[a-zA-Z0-9_-]` max 64 chars
- **Local-only auth**: con `KORE_LOCAL_ONLY=1`, richieste da 127.0.0.1 o testclient saltano la validazione API key
- **Lazy embeddings**: il modello sentence-transformers viene caricato solo al primo uso, non all'avvio del server
- **DB path**: directory `data/` e `logs/` create a runtime, ignorate da git
- **Dashboard inline**: tutto HTML/CSS/JS in un unico file Python (`dashboard.py`), zero build step frontend
- **Client SDK exports**: `kore_memory/__init__.py` esporta `KoreClient`, `AsyncKoreClient` e la gerarchia eccezioni
