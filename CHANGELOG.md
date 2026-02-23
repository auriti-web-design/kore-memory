# Changelog

All notable changes to Kore Memory are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.0] - 2026-02-23

### ⚠️ BREAKING CHANGES

- **Package Renamed** — `src` → `kore_memory` to fix namespace collision (#1)
  - All imports must be updated: `from src import KoreClient` → `from kore_memory import KoreClient`
  - See [MIGRATION-v0.6.md](MIGRATION-v0.6.md) for migration guide
  - Automated migration: `sed -i 's/from src\./from kore_memory./g' *.py`

### 🔧 Fixed

- **#2 (CRITICAL)** — Pagination broken with offset/limit
  - Replaced broken offset/limit with cursor-based pagination
  - No more duplicate/missing results with offset > 0
  - `offset` parameter kept for backwards compat (deprecated)
  - New `cursor` param returns base64 encoded position token
  - Test: 20 records, 4 pages, zero duplicates ✅

- **#1 (CRITICAL)** — Package naming `src/` causes namespace collision
  - Package renamed to `kore_memory` following Python best practices
  - Fixes installation conflicts with other projects using src-layout
  - All internal imports updated

### ✨ Added

- **Cursor-based Pagination** — Reliable pagination for `/search` and `/timeline`
  - `cursor` parameter for next page navigation
  - `has_more` boolean in response
  - Backwards compatible with deprecated `offset`

### 📚 Documentation

- Added `MIGRATION-v0.6.md` with migration guide
- Updated README with new import paths
- Updated all code examples to use `kore_memory`

---

## [0.5.4] - 2026-02-20

### 🔧 Fixed
- **UX Improvement** — `KORE_LOCAL_ONLY=1` di default per localhost. Nessuna API key richiesta per `127.0.0.1`
- **Auto API Key Generation** — Genera automaticamente API key sicura al primo avvio se mancante
- **Installation Experience** — Funziona out-of-the-box dopo `pip install kore-memory && kore`

### ✨ Added
- **JavaScript/TypeScript SDK** — `kore-memory-client` npm package con 17 metodi async, zero runtime dependencies, dual ESM/CJS output, full TypeScript support
- **Error Hierarchy** — 6 classi errore tipizzate (KoreError, KoreAuthError, KoreNotFoundError, etc.)
- **Complete Test Suite** — 44 test per SDK JS con mock fetch, error handling, tutti i metodi API

### 📦 Package
- **Zero Dependencies** — usa fetch nativo, ~6KB minified
- **Dual Output** — ESM + CommonJS con tsup
- **Type Definitions** — .d.ts completi per TypeScript
- **Node 18+** — supporto JavaScript moderno

### 📚 Documentation
- README completo per SDK con esempi TypeScript
- Sezione JS/TS SDK aggiunta al README principale
- Roadmap aggiornato: npm SDK ✅

---

## [0.5.3] - 2026-02-20

### ✨ Added
- **Web Dashboard** — dashboard completa servita da FastAPI su `/dashboard`. HTML inline con CSS + JS vanilla, zero dipendenze extra. 7 sezioni: Overview, Memories, Tags, Relations, Timeline, Maintenance, Backup. Dark theme, responsive, agent selector
- **CSP dinamico** — Content Security Policy allargato solo per `/dashboard` (inline styles/scripts + Google Fonts), restrittivo per tutte le API

### 🧪 Testing
- 7 nuovi test dashboard (route, sezioni, CSP, branding, JS helpers)
- Total test suite: **91 tests** ✅

### 📚 Documentation
- README: aggiunta sezione Web Dashboard con tabella feature, aggiornata roadmap (dashboard completata), aggiunto `/dashboard` alla API reference

---

## [0.5.2] - 2026-02-20

### 🔧 Fixed
- **Public exports** — `KoreClient`, `AsyncKoreClient`, e tutte le eccezioni ora esportati da `src/__init__.py` (`from src import KoreClient`)
- **README imports** — aggiornati tutti gli esempi da `from src.client import` a `from src import`

---

## [0.5.1] - 2026-02-20

### ✨ Added
- **Python SDK** — `KoreClient` (sync) and `AsyncKoreClient` (async) with type-safe wrappers for all 17 API endpoints. Typed exceptions (`KoreAuthError`, `KoreNotFoundError`, `KoreValidationError`, `KoreRateLimitError`, `KoreServerError`). Context manager support (`with` / `async with`). Returns Pydantic models, zero duplication (`src/client.py`)

### 🧪 Testing
- 35 new SDK tests (15 unit + 20 integration via ASGI transport)
- Total test suite: **84 tests** ✅

### 📚 Documentation
- README: added Python SDK section with sync/async examples, error handling, and methods table
- CHANGELOG: updated with SDK details
- Roadmap: Python SDK marked as complete

---

## [0.5.0] - 2026-02-20

### ✨ Added
- **MCP Server** — native Model Context Protocol integration for Claude, Cursor, and any MCP client (`kore-mcp` command). 6 tools: save, search, timeline, decay, compress, export. 1 resource: `kore://health`
- **Tags** — tag any memory, search by tag, agent-scoped. Normalized to lowercase, duplicates ignored (`POST/DELETE/GET /memories/{id}/tags`, `GET /tags/{tag}/memories`)
- **Relations** — bidirectional knowledge graph between memories. Cross-agent linking prevented (`POST/GET /memories/{id}/relations`)
- **Batch API** — save up to 100 memories in a single request (`POST /save/batch`)
- **TTL (Time-to-Live)** — set `ttl_hours` on save for auto-expiring memories. Expired memories filtered from search, timeline, export. Manual cleanup via `POST /cleanup`, automatic cleanup integrated into decay pass
- **Export / Import** — full JSON backup of active memories (`GET /export`, `POST /import`). Expired memories excluded from export. Import skips invalid records gracefully
- **Pagination** — `offset` + `has_more` on `/search` and `/timeline` endpoints
- **Centralized config** — all env vars in `src/config.py` (9 configurable options)
- **Vector index cache** — in-memory embedding cache with per-agent invalidation for faster semantic search
- **Python SDK** — `KoreClient` (sync) and `AsyncKoreClient` (async) with type-safe wrappers for all 17 API endpoints. Typed exceptions (`KoreAuthError`, `KoreNotFoundError`, `KoreValidationError`, `KoreRateLimitError`, `KoreServerError`). Context manager support (`with` / `async with`). Returns Pydantic models, zero duplication
- **OOM protection** — embedding input capped at `KORE_MAX_EMBED_CHARS` (default 8000)
- **Concurrency locks** — non-blocking threading locks for decay and compression passes

### 🗄️ Database
- Added `memory_tags` table (memory_id, tag) with tag index
- Added `memory_relations` table (source_id, target_id, relation) with bidirectional indexes
- Added `expires_at` column to memories table with migration for existing DBs

### 🧪 Testing
- Test suite expanded from 17 to **84 tests** covering all P3 features + SDK
- Tests for: batch API, tags (7), relations (5), TTL/cleanup (8), export/import (5), pagination (3)
- SDK tests: 15 unit (helpers, exceptions, class structure) + 20 integration (all endpoints via ASGI transport)
- Rate limiter reset in `setup_method` to prevent 429 interference between test classes

### 📚 Documentation
- README rewritten: comparison table (+5 features), key features (+5 sections), complete API reference organized by category, MCP Server section with Claude/Cursor config, Python SDK section with sync/async examples, full env var documentation, updated roadmap

### 📦 Installation
- New optional dependency group: `mcp` (`pip install kore-memory[mcp]`)
- New entry point: `kore-mcp` for MCP server

---

## [0.4.0] - 2026-02-20

### 🔐 Security
- Added rate limiting middleware (10 requests/second per IP)
- Implemented CORS middleware with configurable origins
- Added comprehensive security headers (X-Frame-Options, X-Content-Type-Options, CSP)
- Added global error handler to prevent information leakage
- Enabled SSL verification on httpx client (controlled via `WP_SSL_VERIFY` env var)
- Sanitized credentials in maintenance templates

### 🗄️ Database
- Fixed `KORE_DB_PATH` to resolve at runtime instead of import-time
- Switched all timestamps to UTC (via `datetime.now(UTC)`)
- Improved FTS5 query sanitization (prevent SQL injection)
- Added batch decay updates for better performance
- Made embedding generation resilient to failures

### 🧪 Testing
- Fixed test suite: explicit `init_db()` call before TestClient initialization
- All 17 tests passing ✅

### 📚 Documentation
- Added `CLAUDE.md` (project context for AI assistants)
- Added competitive analysis vs Mem0, Letta, Zep
- Improved README with deployment section

### 🛠️ Fixes
- Fixed CLI bug: corrected module path from `kore.src.main:app` to `src.main:app` (ModuleNotFoundError)
- Created `kore-daemon.sh` for proper daemonization with `.env` support
- Updated `start.sh` to load environment variables correctly

### ⚡ Performance
- Optimized memory decay calculations
- Batch processing for compression operations

---

## [0.3.1] - 2026-02-19

### ✨ Added
- Semantic search with multilingual embeddings (50+ languages)
- Memory compression (auto-merge similar memories)
- Timeline API (chronological memory traces)
- Agent namespace isolation
- Auto-importance scoring (no LLM required)
- Memory decay using Ebbinghaus forgetting curve

### 🔐 Security
- API key authentication
- Agent-scoped access control
- Timing-safe key comparison

### 📦 Installation
- Published to PyPI as `kore-memory`
- CLI command `kore` available after install
- Optional `[semantic]` extras for embeddings

---

## [0.3.0] - 2026-02-18

### 🎉 Initial Public Release
- Core memory storage with SQLite + FTS5
- REST API (FastAPI)
- Basic search and CRUD operations
- Offline-first architecture
- Zero external dependencies for core features

---

## Version Naming

- **0.5.x** — MCP, tags, relations, TTL, batch API, Python SDK
- **0.4.x** — Security & stability improvements
- **0.3.x** — Semantic search & compression
- **0.2.x** — Internal testing (not released)
- **0.1.x** — Initial development

---

[0.5.3]: https://github.com/auriti-web-design/kore-memory/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/auriti-web-design/kore-memory/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/auriti-web-design/kore-memory/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/auriti-web-design/kore-memory/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/auriti-web-design/kore-memory/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/auriti-web-design/kore-memory/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/auriti-web-design/kore-memory/releases/tag/v0.3.0
