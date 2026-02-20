# Changelog

All notable changes to Kore Memory are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- **0.4.x** — Security & stability improvements
- **0.3.x** — Semantic search & compression
- **0.2.x** — Internal testing (not released)
- **0.1.x** — Initial development

---

[0.4.0]: https://github.com/auriti-web-design/kore-memory/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/auriti-web-design/kore-memory/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/auriti-web-design/kore-memory/releases/tag/v0.3.0
