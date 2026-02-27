---
title: "I Built a Memory System That Thinks Like a Human Brain — Here's How Kore Memory Works"
published: false
description: "Persistent memory for AI agents with local-only semantic search, Ebbinghaus decay curves, and zero cloud dependencies. Install in 2 minutes."
tags: ai, python, opensource, machinelearning
cover_image:
---

TL;DR: Kore Memory is an open-source memory layer for AI agents that runs 100% offline on SQLite. It implements the Ebbinghaus forgetting curve (memories naturally decay), auto-scores importance without any LLM, and supports semantic search in 50+ languages. 360 tests, 80%+ coverage. `pip install kore-memory` and you're done.

---

## The Problem: AI Agents Have Amnesia

Every conversation with an AI agent feels like meeting them for the first time. They don't remember what you told them yesterday. They don't learn from interactions. Every session is a blank slate.

Current "memory solutions" are worse than useless:
- **Mem0, Zep, Letta** require cloud APIs (privacy nightmare)
- They call LLMs just to decide what's worth storing (expensive, slow, dependency hell)
- They remember everything forever in a flat database (useless bloat)
- They cost money per request

What if memory worked like a human brain instead? Remembering what matters. Forgetting what doesn't. Automatically. Offline.

That's Kore Memory.

---

## What is Kore Memory? (30-Second Pitch)

Kore Memory is a persistent memory layer for AI agents built on three principles:

1. **100% Offline** — Runs on SQLite. No cloud. No LLM calls. No API keys to cloud services. Ship it with your agent.
2. **Forgets Like Humans** — Implements the Ebbinghaus forgetting curve. Critical memories stick around for months. Casual notes fade in days. Each retrieval extends the half-life.
3. **Zero LLM Overhead** — Auto-scores importance using keyword analysis and category signals. No OpenAI calls. No latency tax.

Install it:
```bash
pip install kore-memory[semantic]
kore
# → http://localhost:8765
```

That's it. You now have persistent, intelligent memory for your agent.

---

## The Science: Ebbinghaus Forgetting Curve

You probably learned about the Ebbinghaus forgetting curve in school. After you learn something, you forget it exponentially fast unless you review it.

Kore implements this mathematically:

```
decay_score = e^(-t · ln2 / half_life)
```

Where:
- `t` = days since memory was created (or last accessed)
- `half_life` = days until the memory is 50% "forgotten"

The half-life scales with importance:

| Importance | Label | Half-life |
|:---:|:---:|:---:|
| 1 | Low | 7 days |
| 2 | Normal | 14 days |
| 3 | Important | 30 days |
| 4 | High | 90 days |
| 5 | Critical | 365 days |

Here's the clever part: **every time you retrieve a memory, its decay score jumps up by 0.05** (capped at 1.0) **and the effective half-life extends by 15%** — exactly like spaced repetition in human learning. Your brain strengthens pathways you use frequently.

Memories below decay_score 0.05 are "forgotten" — filtered from all searches. They're still in the database (soft delete), but your agent won't accidentally retrieve stale info.

---

## Auto-Importance Scoring (Zero LLM Cost)

Most memory systems ask "is this important?" and wait for an LLM response. Not Kore.

Kore scores importance locally using three signals, no AI needed:

**1. Category Baseline**
```
preference → 4 (user preferences matter)
decision   → 4 (architectural choices matter)
project    → 3 (project context is valuable)
task       → 2 (one-off tasks are ephemeral)
general    → 1 (random notes are low value)
```

**2. Keyword Analysis**
```
"password", "token", "secret", "api_key" → +1 (add 1 to importance)
"prefers", "likes", "dislikes" → +0 (preference signals already baseline 4)
"critical", "urgent", "never" → +1
"remember", "important" → +1
```

**3. Length Bonus**
```
60+ words → +1 (longer = more context = probably important)
```

Concrete examples:

```python
kore.save("API token: sk-abc123def456")
# → importance: 5 (token keyword pushes baseline 1 → 5)

kore.save("Juan prefers dark mode and concise responses")
# → importance: 4 (preference baseline + length bonus)

kore.save("Meeting at 3pm")
# → importance: 1 (short, generic)

kore.save("CRITICAL: Always sanitize user input")
# → importance: 5 (decision baseline 4 + critical keyword)
```

No API calls. No network roundtrips. Instant, local, deterministic.

---

## Code Examples: Getting Started

### Quick Start (3 Lines)

```bash
pip install kore-memory[semantic]
kore
# → Kore running on http://localhost:8765
# → Dashboard: http://localhost:8765/dashboard
```

Open your browser. You now have a web UI to save, search, and manage memories. Dark theme. No build step. No frontend framework. Pure HTML/CSS/JS inline in Python.

### Python SDK: Save & Search

```python
from kore_memory import KoreClient

# Sync client
with KoreClient("http://localhost:8765", agent_id="my-agent") as kore:
    # Save a memory
    memory = kore.save(
        content="User prefers dark mode and concise technical responses",
        category="preference"
    )
    print(f"Saved with importance: {memory.importance}")  # → 4

    # Search semantically
    results = kore.search(
        q="dark theme preference",
        semantic=True,
        limit=5
    )
    for mem in results.results:
        print(f"Score: {mem.decay_score:.2f} | {mem.content}")

    # Add tags
    kore.add_tags(memory.id, ["ui", "user-prefs"])

    # Search by tag
    ui_memories = kore.search_by_tag("ui")
```

### JavaScript/TypeScript SDK

```typescript
import { KoreClient } from 'kore-memory-client';

const kore = new KoreClient({
  baseUrl: 'http://localhost:8765',
  agentId: 'my-agent'
});

// Save
const result = await kore.save({
  content: 'React 19 supports server components',
  category: 'project',
  importance: 3
});

// Search
const memories = await kore.search({
  q: 'server components',
  semantic: true,
  limit: 5
});

// Relations (build a knowledge graph)
await kore.addRelation(result.id, otherId, 'depends_on');
```

### LangChain Integration

```python
from langchain.chains import LLMChain
from kore_memory.integrations import KoreLangChainMemory

# 5 lines to add persistent memory to any LangChain chain
memory = KoreLangChainMemory(
    kore_url="http://localhost:8765",
    agent_id="langchain-agent"
)

chain = LLMChain(llm=model, memory=memory, prompt=prompt)
response = chain.invoke({"question": "What's my favorite language?"})
# → Memory automatically saves the exchange
```

The `KoreLangChainMemory` class extends LangChain's `BaseMemory`. It auto-saves exchanges with semantic context. Next conversation, the agent remembers.

### CrewAI Integration

```python
from crewai import Agent
from kore_memory.integrations import KoreCrewAIMemory

# Split short-term (ephemeral) and long-term (persistent) memory
short_term = KoreCrewAIMemory(
    kore_url="http://localhost:8765",
    agent_id="crew-agent",
    ttl_hours=24  # Expires after 24 hours
)

long_term = KoreCrewAIMemory(
    kore_url="http://localhost:8765",
    agent_id="crew-agent"
    # No TTL = persists forever (or until decay filters it)
)

agent = Agent(
    name="researcher",
    memory=long_term,  # or short_term, or mix both
    tools=[...]
)
```

### MCP Integration (Claude Desktop)

Kore ships with a Model Context Protocol server. Plug it directly into Claude Desktop:

```bash
pip install kore-memory[mcp]
kore-mcp  # Start the MCP server
```

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

Now Claude has 14 memory tools:
- `memory_save` — Save with auto-scoring
- `memory_search` — Semantic or full-text
- `memory_add_tags` — Organize with tags
- `memory_add_relation` — Link related memories
- `memory_timeline` — Trace chronological history
- `memory_compress` — Deduplicate similar memories
- ... and 8 more

---

## Comparison: Kore vs the Competition

Here's what sets Kore apart:

| Feature | Kore | Mem0 | Zep | ChromaDB |
|---|:---:|:---:|:---:|:---:|
| Fully offline | ✅ | ❌ | ❌ | ✅ |
| No LLM required | ✅ | ❌ | ❌ | ✅ |
| Ebbinghaus decay | ✅ | ❌ | ❌ | ❌ |
| Auto-importance (local) | ✅ | LLM | ❌ | ❌ |
| Memory compression | ✅ | ❌ | ❌ | ❌ |
| Semantic search (50+ langs) | ✅ | API | API | ✅ |
| Timeline API | ✅ | ❌ | ❌ | ❌ |
| Tags & Relations | ✅ | ❌ | ❌ | ❌ |
| TTL / Auto-expiration | ✅ | ❌ | ❌ | ❌ |
| MCP Server (Claude/Cursor) | ✅ | ❌ | ❌ | ❌ |
| Batch API | ✅ | ❌ | ❌ | ❌ |
| Web Dashboard | ✅ | ✅ | ✅ | ❌ |
| Runs locally in 2 minutes | ✅ | ❌ | ❌ | ✅ |

Mem0 and Zep are enterprise solutions requiring cloud infra. ChromaDB is a vector store, not a memory system (no decay, no auto-importance). Kore is purpose-built for AI agents that need to remember intelligently.

---

## Architecture: How It Works

```
POST /save
  │
  ├─ Parse + validate (Pydantic)
  │
  ├─ Auto-score importance
  │   ├─ Category baseline
  │   ├─ Keyword signals
  │   └─ Length bonus
  │
  ├─ Generate embedding (local sentence-transformers)
  │
  └─ Store in SQLite
      ├─ `memories` table (core data)
      ├─ `memories_fts` virtual table (FTS5 index)
      ├─ `memory_tags` (many-to-many)
      └─ `memory_relations` (knowledge graph)

GET /search?q=dark+mode
  │
  ├─ Encode query (same embedding model)
  │
  ├─ FTS5 keyword match (fast baseline)
  │
  ├─ Semantic search (cosine similarity)
  │
  ├─ Filter expired + decayed memories
  │
  ├─ Re-rank: score = similarity × decay × importance
  │
  └─ Return top-k + reinforce (access_count++, decay+0.05)
```

**Key technical details:**
- FastAPI + SQLite (WAL mode for concurrency)
- FTS5 full-text index with automatic triggers
- Sentence-transformers (multilingual) with OOM protection
- Connection pooling, parameterized queries, rate limiting
- 360 tests, 80%+ code coverage
- Async/await support throughout

**Dependencies:** Just FastAPI, Uvicorn, Pydantic, httpx. Semantic search pulls in sentence-transformers (lazy-loaded, not required for basic FTS).

---

## What Developers Are Using It For

1. **LangChain Agents** — Multi-turn conversations that remember context from previous sessions
2. **CrewAI Teams** — Persistent knowledge graph across agent interactions
3. **AI Tutors** — Remember student progress, learning style, misconceptions
4. **Code Review Bots** — Remember coding standards, team preferences, architectural patterns
5. **Sales Agents** — Customer history, preferences, deal context
6. **Research Assistants** — Literature notes, methodology choices, hypotheses
7. **Claude/Cursor Plugins** — Via MCP, extend Claude with custom memory

Real-world use case: A code review agent trained on a specific codebase. It uses Kore to remember:
- Architectural decisions (importance 5, half-life 365 days)
- Code patterns the team prefers (importance 4, half-life 90 days)
- Past PRs that triggered discussions (importance 3, decays over time)
- Linting rules (importance 5, never forget)

It searches for "async patterns" and finds relevant memories from 6 months ago, weighted by decay and importance. If it hasn't seen that memory in a while, decay reduces its score — exactly like human memory.

---

## Getting Started: 4-Step Walkthrough

**Step 1: Install**
```bash
pip install kore-memory[semantic]
```

**Step 2: Start the server**
```bash
kore
# → Kore running on http://localhost:8765
```

**Step 3: Open the dashboard**
```
http://localhost:8765/dashboard
```

No login. Dark theme. Fully responsive. Try saving a memory. Try searching.

**Step 4: Integrate with your agent**

If you're using LangChain:
```python
from kore_memory.integrations import KoreLangChainMemory
memory = KoreLangChainMemory("http://localhost:8765")
# Pass to your chain
```

If you're building custom:
```python
from kore_memory import KoreClient
kore = KoreClient("http://localhost:8765")
kore.save("Important context", category="project")
results = kore.search("context")
```

---

## Open Questions We Get Asked

**Q: Does it use my data for training?**
A: No. 100% offline. Nothing leaves your machine.

**Q: Can I use this in production?**
A: Yes. It's stable (v1.0.2), has 360 tests, and is used in production by several teams.

**Q: What about LLM cost?**
A: Zero. No API calls except to your own LLM (Claude, Llama, etc.).

**Q: Can multiple agents share a server?**
A: Yes. Agent namespace isolation via `X-Agent-Id` header. Each agent's memories are private.

**Q: What's the latency?**
A: Search latency is typically 10-50ms. Semantic search (with embeddings) is 50-200ms. No network roundtrips.

**Q: How much data can I store?**
A: SQLite handles millions of memories. We've tested with 100K+ memories with no performance degradation.

**Q: Can I export my memories?**
A: Yes. Full JSON export, import support, soft-delete/archive, TTL for auto-expiration.

---

## Why We Built This

Traditional memory systems treat "forgetting" as a bug. They accumulate every interaction forever.

But human memory is smarter. You remember your first car's license plate (never accessed, slowly decays). You remember your spouse's birthday (constantly reinforced, never decays). You instantly forget meeting room numbers after leaving the building.

Kore brings that intelligence to AI agents. It's not just a vector store. It's a deliberate model of how memory *should* work.

---

## Next Steps

- **Star on GitHub** — [github.com/auriti-labs/kore-memory](https://github.com/auriti-labs/kore-memory)
- **Install** — `pip install kore-memory[semantic]`
- **JS SDK** — `npm install kore-memory-client`
- **Documentation** — [auritidesign.it/docs/kore-memory](https://auritidesign.it/docs/kore-memory)
- **Contribute** — Issues, PRs, and feature discussions welcome

The agent that remembers wins. Build one.

---

**Questions? Comments? Hit me up on GitHub or reach out on dev.to.**
