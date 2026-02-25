# Migration Guide: v0.5.x → v0.6.0

## ⚠️ Breaking Changes

### Package Renamed: `src` → `kore_memory`

**Why:** The package was incorrectly named `src`, causing namespace collisions with other projects using the src-layout pattern.

**Impact:** All imports must be updated.

---

## 🔧 How to Migrate

### 1. Update your imports

**Before (v0.5.x):**
```python
from src import KoreClient, AsyncKoreClient
from src.models import MemorySaveRequest
from src.database import init_db
```

**After (v0.6.0):**
```python
from kore_memory import KoreClient, AsyncKoreClient
from kore_memory.models import MemorySaveRequest
from kore_memory.database import init_db
```

### 2. Public API (recommended)

If you're using the public exports (recommended), migration is simple:

```python
# v0.5.x
from src import KoreClient

# v0.6.0
from kore_memory import KoreClient
```

### 3. Automated migration

Run this command in your project root:

```bash
find . -name "*.py" -exec sed -i 's/from src\./from kore_memory./g' {} \;
find . -name "*.py" -exec sed -i 's/import src\./import kore_memory./g' {} \;
```

---

## ✅ Non-Breaking Changes

All these work **exactly the same** in v0.6.0:

- REST API endpoints (`/search`, `/save`, `/timeline`, etc.)
- Database schema (no migrations needed)
- Configuration (`.env`, `config.py`)
- CLI commands (`kore`, `kore-mcp`)
- MCP server tools

---

## 🆕 New in v0.6.0

### Cursor-based pagination (fixes #2)

The broken `offset`/`limit` pagination has been replaced with cursor-based pagination:

**Before (v0.5.x):**
```python
# ❌ Could skip/duplicate results
response = client.search("query", limit=10, offset=20)
```

**After (v0.6.0):**
```python
# ✅ Reliable pagination
response = client.search("query", limit=10)
next_page = client.search("query", limit=10, cursor=response.cursor)
```

**Backwards compatibility:** The `offset` parameter still works but is deprecated.

---

## 📦 Installation

```bash
pip install --upgrade kore-memory
```

---

## 🐛 Issues Fixed

- **#1** - Package naming `src/` causes namespace collision (CRITICAL)
- **#2** - Pagination broken with offset/limit (CRITICAL)

---

## 📞 Need Help?

- [Open an issue](https://github.com/auriti-labs/kore-memory/issues)
- [Read the docs](https://github.com/auriti-labs/kore-memory#readme)
