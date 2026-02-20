# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kore Memory is a persistent memory layer for AI agents (Python 3.11+, FastAPI, SQLite). Runs fully offline — no LLM calls, no cloud APIs. Implements Ebbinghaus forgetting curve decay, local auto-importance scoring, semantic search via sentence-transformers, and memory compression.

Published on PyPI as `kore-memory` (v0.3.1). MIT license.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[semantic,dev]"

# Run server
kore                                    # localhost:8765
kore --port 9000 --reload               # dev mode
./start.sh                              # background (PID in logs/kore.pid)

# Tests (17 test, pytest)
pytest tests/ -v
pytest tests/test_api.py::TestSave -v           # singola classe
pytest tests/test_api.py::TestSave::test_save_basic -v  # singolo test

# Build per PyPI
pip install build && python -m build
```

No linter/formatter configurati. No CI/CD.

## Architecture

```
Request → FastAPI (main.py) → Auth (auth.py) → Pydantic (models.py) → Repository (repository.py) → SQLite (database.py)
                                                                            ↕               ↕            ↕
                                                                      scorer.py      embedder.py    decay.py
                                                                                                  compressor.py
```

**Entry points:**
- `src/cli.py` → comando `kore`, avvia uvicorn su `src.main:app`
- `src/main.py` → FastAPI app con lifespan (init_db), tutti gli endpoint

**Moduli core (src/):**

| Modulo | Responsabilità |
|--------|---------------|
| `main.py` | FastAPI app, endpoint REST, lifespan |
| `repository.py` | Logica business: save, search (FTS5 + semantic), delete, decay pass, timeline. Modulo più grande (~270 righe) |
| `database.py` | SQLite connection (WAL mode), schema `memories` + `memories_fts` (FTS5), indici, context manager |
| `decay.py` | Curva di Ebbinghaus: `decay = e^(-t·ln2/half_life)`. Half-life 7gg (importance 1) → 365gg (importance 5). +15% per ogni retrieval |
| `scorer.py` | Auto-scoring importance 1-5 senza LLM: keyword signals, category baseline, length bonus |
| `embedder.py` | Wrapper sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dim). Lazy-loaded con LRU cache |
| `compressor.py` | Merge memorie con cosine similarity > 0.88. Clustering greedy, marca originali con `compressed_into` |
| `auth.py` | API key auto-generata (secrets.token_urlsafe), timing-safe comparison, agent namespace isolation via header `X-Agent-Id` |
| `models.py` | Pydantic v2 schemas. Categorie: general, project, trading, finance, person, preference, task, decision |

**Database schema (`memories` table):**
- Colonne principali: `id`, `agent_id`, `content`, `category`, `importance` (1-5), `decay_score` (0.0-1.0), `access_count`, `embedding` (JSON blob), `compressed_into` (FK self-ref)
- FTS5 virtual table `memories_fts` su content + category con trigger automatici
- Indici su: agent_id, decay_score, compressed, category, importance, created_at

**Search flow:**
1. Se semantic=True e embeddings disponibili → cosine similarity su tutti gli embeddings (O(n))
2. Altrimenti → FTS5 con wildcard
3. Filtra memorie con `decay_score < 0.05` (dimenticate)
4. Re-rank per `effective_score = decay × importance`
5. Reinforcement: `access_count++`, `decay_score += 0.05`

## Test Structure

File unico `tests/test_api.py` — usa `TestClient` FastAPI (in-process, no network). Ogni test crea un DB temporaneo (`KORE_DB_PATH` env var), usa `KORE_LOCAL_ONLY=1` per skip auth, isola con `X-Agent-Id: test-agent`.

Classi: TestHealth, TestSave, TestAuth, TestAgentIsolation, TestSearch, TestDecay, TestCompress, TestTimeline, TestDelete.

## Environment Variables

| Variabile | Default | Uso |
|-----------|---------|-----|
| `KORE_API_KEY` | auto-generata in `data/.api_key` | Override API key |
| `KORE_LOCAL_ONLY` | `"1"` | Skip auth per localhost |
| `KORE_DB_PATH` | `data/memory.db` | Path DB (usato nei test per temp DB) |

## Key Patterns

- **Agent isolation**: tutte le query DB filtrano per `agent_id`. Header `X-Agent-Id`, default `"default"`, sanitizzato a `[a-zA-Z0-9_-]` max 64 chars
- **Local-only auth**: con `KORE_LOCAL_ONLY=1`, richieste da 127.0.0.1 o testclient saltano la validazione API key
- **Lazy embeddings**: il modello sentence-transformers viene caricato solo al primo uso, non all'avvio del server
- **DB path**: directory `data/` e `logs/` create a runtime, ignorate da git
