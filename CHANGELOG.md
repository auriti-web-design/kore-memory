# Changelog

All notable changes to Kore Memory are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.9.0] - 2026-02-24

### Theme: "Intelligence"

### Added
- **Session/Conversation Tracking**: New `sessions` table, `X-Session-Id` header support, auto-create sessions on save. Endpoints: `POST /sessions`, `GET /sessions`, `GET /sessions/{id}/memories`, `GET /sessions/{id}/summary`, `POST /sessions/{id}/end`, `DELETE /sessions/{id}`. Sessions UI tab in dashboard.
- **Memory Graph Visualization**: New "Graph" tab in dashboard with force-directed layout (vanilla JS canvas, zero dependencies). Nodes colored by category, sized by importance. Hover tooltips, edge labels, SVG export. Category filter support.
- **Entity Extraction** (`kore-memory[nlp]`): Optional spaCy NER for PERSON, ORG, GPE, DATE, MONEY, PRODUCT entities. Regex fallback for emails, URLs, dates, monetary values (no extra deps). Auto-tagging with `entity:type:value` format. `GET /entities` endpoint. Enable with `KORE_ENTITY_EXTRACTION=1`.
- **Importance Auto-Tuning**: Learns from access patterns — boosts frequently accessed memories (access_count >= 5), reduces never-accessed memories after 30 days. `POST /auto-tune`, `GET /stats/scoring` endpoints. Enable with `KORE_AUTO_TUNE=1`. Thread-safe with dedicated lock.
- **Event Audit Log**: Persistent event logging to `event_logs` table. Captures all memory lifecycle events (save, delete, update, compress, decay, archive, restore). `GET /audit` endpoint with filters (event type, since, limit). Auto-cleanup support. Enable with `KORE_AUDIT_LOG=1`.
- **Agent Discovery**: `GET /agents` endpoint lists all agent IDs with memory count and last activity. Dashboard agent selector now shows datalist with existing agents.
- **Dashboard Sessions tab**: View sessions, session summary (categories, avg importance, memory count), session memories list.
- 77 new tests (17 sessions + 20 auto-tuner + 17 audit + 23 entities), total: 242

### Changed
- `save_memory()` now accepts optional `session_id` parameter
- Database schema: added `sessions` table, `event_logs` table, `session_id` column on memories
- CSP fix: removed all 26 inline onclick handlers, replaced with addEventListener + event delegation

---

## [0.8.0] - 2026-02-24

**"Developer Experience" — Framework integrations, dashboard overhaul, CI/CD maturity.**

### ✨ Added

- **LangChain Integration** — `KoreLangChainMemory` extending `BaseMemory` for drop-in use with LangChain chains
  - `load_memory_variables()` retrieves relevant context via semantic search
  - `save_context()` auto-saves conversation turns with importance scoring
  - `clear()` is a no-op — Kore handles decay naturally
  - Configurable: `memory_key`, `input_key`, `output_key`, `k`, `semantic`, `category`
  - Install: `pip install 'kore-memory[langchain]'`

- **CrewAI Integration** — `KoreCrewAIMemory` as a memory provider for CrewAI agents
  - `save()` / `search()` for general memory operations
  - `save_short_term()` — importance=1, TTL=24h for ephemeral context
  - `save_long_term()` — importance=4+, no TTL for persistent knowledge
  - Install: `pip install 'kore-memory[crewai]'`

- **Dashboard UX Overhaul** — Major UI improvements:
  - Light/dark theme toggle (persisted in localStorage)
  - Keyboard shortcuts: `/` search, `N` new memory, `Esc` dismiss, `1-9` navigation, `T` theme, `?` help
  - Search filters panel: category, importance range, date range
  - Expandable memory cards with full detail view (tags, relations, decay, access count)
  - Inline memory editing (click Edit to modify content, category, importance)
  - CSV + JSON export from search results
  - New **Archive tab** — view and restore archived memories
  - New **Metrics tab** — category distribution, importance histogram, decay distribution, system stats
  - Loading spinners on all API calls (search, save, maintenance, export, import)
  - Toast notifications with success/error icons
  - Empty state illustrations with helpful guidance
  - ARIA labels, `role` attributes, skip-to-content link, `aria-live` regions
  - Keyboard-navigable sidebar with `tabindex` and `aria-current`

- **CI/CD Improvements**:
  - Coverage job with `pytest-cov` (warns if <80%)
  - JS SDK test job (Node 20, vitest)
  - JS SDK build auto-triggered on `v*` tags
  - Coverage report uploaded as GitHub Actions artifact

- **Quick Wins**:
  - `__version__` exported from `kore_memory` package
  - `CONTRIBUTING.md` guide for OSS contributors
  - GitHub issue templates (bug report + feature request, YAML forms)
  - Pull request template with checklist
  - Example scripts: `basic_usage.py`, `langchain_example.py`, `async_usage.py`

### 📦 SDK

- JavaScript SDK updated to v0.8.0
- New optional dependency groups: `langchain`, `crewai`
- `pytest-cov` added to dev dependencies

### 🧪 Testing

- 28 new LangChain integration tests (mocked client, graceful import fallback)
- 19 new CrewAI integration tests (short/long-term patterns, lifecycle)
- Total test suite: **165 tests** (was 118)

---

## [0.7.0] - 2026-02-24

**Resolves ALL 30 open GitHub issues.**

### ⚡ Performance
- **#13** — Semantic search O(n) → numpy batch dot product (10-50x faster)
- **#14** — Compressor O(n²) → numpy matrix multiplication for pairwise similarity
- **#26** — Embeddings serialized as binary (`struct.pack`) instead of JSON text (~50% smaller)
- **#19** — Batch save uses `embed_batch()` for single model invocation instead of N calls
- **#27** — SQLite connection pooling (Queue-based, pool size 4)

### 🔐 Security
- **#12** — Rate limiter hardened: threading lock, `X-Forwarded-For`/`X-Real-IP` support, periodic bucket cleanup (prevents memory leak)
- **#16** — Dashboard requires authentication for non-localhost requests
- **#17** — CSP upgraded from `unsafe-inline` to nonce-based scripts (per-request nonce via `secrets.token_urlsafe`)
- **#18** — CI security scanning: bandit SAST + pip-audit dependency audit
- **#28** — Shell scripts: `.env` loading replaced with safe parser (no arbitrary code execution)

### ✨ Added
- **#15** — `PUT /memories/{id}` — update memory content, category, importance with automatic embedding regeneration
- **#20** — Event system — in-process lifecycle hooks (MEMORY_SAVED, DELETED, UPDATED, COMPRESSED, DECAYED, ARCHIVED, RESTORED)
- **#21** — Storage abstraction — `MemoryStore` Protocol with 16 method signatures for future PostgreSQL support
- **#22** — MCP server expanded from 6 to 14 tools: added delete, update, batch save, tags, search by tag, relations, cleanup, import
- **#24** — Dashboard HTML extracted from Python into `templates/dashboard.html` (dashboard.py: 1208 → 75 lines)
- **#29** — Soft-delete: `POST /memories/{id}/archive`, `POST /memories/{id}/restore`, `GET /archive`
- **#30** — Prometheus metrics endpoint: `GET /metrics` with memory counts, search latency, decay stats
- **#31** — Static type checking: mypy configured, `py.typed` PEP 561 marker

### 🧪 Testing
- **#23** — MCP server test suite: 32 tests across 12 test classes covering all 14 tools
- **#25** — Test fixtures: `conftest.py` with autouse rate limiter reset, isolated DB per test
- **#7** — CI now tests semantic search with sentence-transformers (separate job with model caching)
- Total test suite: **118 tests** (was 91)

### 📦 SDK
- JavaScript SDK updated to v0.7.0: added `update()`, `archive()`, `restore()`, `getArchived()`, `metrics()` methods
- Cursor-based pagination support in search/timeline options

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

- **0.8.x** — Developer experience, LangChain/CrewAI, dashboard UX
- **0.7.x** — Performance, security, 30 issues resolved
- **0.6.x** — Package rename, cursor-based pagination
- **0.5.x** — MCP, tags, relations, TTL, batch API, Python SDK
- **0.4.x** — Security & stability improvements
- **0.3.x** — Semantic search & compression
- **0.2.x** — Internal testing (not released)
- **0.1.x** — Initial development

---

[0.8.0]: https://github.com/auriti-labs/kore-memory/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/auriti-labs/kore-memory/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/auriti-labs/kore-memory/compare/v0.5.4...v0.6.0
[0.5.4]: https://github.com/auriti-labs/kore-memory/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/auriti-labs/kore-memory/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/auriti-labs/kore-memory/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/auriti-labs/kore-memory/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/auriti-labs/kore-memory/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/auriti-labs/kore-memory/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/auriti-labs/kore-memory/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/auriti-labs/kore-memory/releases/tag/v0.3.0
