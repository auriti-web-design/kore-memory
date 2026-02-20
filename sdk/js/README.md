# Kore Memory Client

JavaScript/TypeScript client for [Kore Memory](https://github.com/auriti-web-design/kore-memory) - the memory layer that thinks like a human.

## Features

- 🔥 **Zero runtime dependencies** - uses native `fetch`
- 📦 **Dual package** - ESM + CommonJS support
- 🏷️ **Full TypeScript support** - complete type definitions
- 🚀 **17 async methods** - covers all Kore Memory REST APIs
- ⚡ **Lightweight** - ~6KB minified
- 🛡️ **Error handling** - typed error hierarchy
- 🌐 **Node 18+** - modern JavaScript support

## Installation

```bash
npm install kore-memory-client
```

## Quick Start

```typescript
import { KoreClient } from 'kore-memory-client';

const kore = new KoreClient({
  baseUrl: 'http://localhost:8765',
  agentId: 'my-agent',
  apiKey: 'your-api-key' // optional for localhost
});

// Save a memory
const result = await kore.save({
  content: 'User prefers dark mode',
  category: 'preference',
  importance: 4
});

// Search memories
const memories = await kore.search({
  q: 'dark mode',
  limit: 5,
  semantic: true
});

console.log(memories.results);
```

## Configuration

```typescript
const kore = new KoreClient({
  baseUrl?: string;    // default: 'http://localhost:8765'
  agentId?: string;    // default: 'default'
  apiKey?: string;     // optional, required for non-localhost
  timeout?: number;    // default: 30000ms
});
```

## API Methods

### Core Operations

```typescript
// Save memory
await kore.save({
  content: string,
  category?: Category,     // 'general' | 'project' | 'task' | etc.
  importance?: number,     // 1-5, 1=auto-scored
  ttl_hours?: number      // auto-expire after N hours
});

// Batch save (up to 100)
await kore.saveBatch([
  { content: 'Memory 1', category: 'project' },
  { content: 'Memory 2', category: 'task' }
]);

// Search memories
await kore.search({
  q: string,
  limit?: number,         // default: 5
  offset?: number,        // pagination
  category?: Category,    // filter by category
  semantic?: boolean      // default: true
});

// Timeline for subject
await kore.timeline({
  subject: string,
  limit?: number,
  offset?: number
});

// Delete memory
await kore.delete(memoryId: number);
```

### Tags & Relations

```typescript
// Add tags
await kore.addTags(memoryId, ['react', 'frontend']);

// Get tags
await kore.getTags(memoryId);

// Remove tags
await kore.removeTags(memoryId, ['old-tag']);

// Search by tag
await kore.searchByTag('react', 10);

// Add relation
await kore.addRelation(memoryId, targetId, 'depends_on');

// Get relations
await kore.getRelations(memoryId);
```

### Maintenance

```typescript
// Run decay pass (Ebbinghaus forgetting)
await kore.decayRun();

// Compress similar memories
await kore.compress();

// Cleanup expired memories
await kore.cleanup();
```

### Backup

```typescript
// Export all memories
const backup = await kore.exportMemories();

// Import memories
await kore.importMemories(backup.memories);
```

### Utility

```typescript
// Health check
const health = await kore.health();
console.log(health.capabilities.semantic_search);
```

## Error Handling

The client provides a typed error hierarchy:

```typescript
import { 
  KoreError,
  KoreAuthError,
  KoreNotFoundError,
  KoreValidationError,
  KoreRateLimitError,
  KoreServerError
} from 'kore-memory-client';

try {
  await kore.save({ content: 'ab' }); // too short
} catch (error) {
  if (error instanceof KoreValidationError) {
    console.log('Validation failed:', error.detail);
  } else if (error instanceof KoreAuthError) {
    console.log('Authentication failed');
  }
}
```

## TypeScript Support

Full type definitions included:

```typescript
import type { 
  MemoryRecord,
  MemorySaveResponse,
  MemorySearchResponse,
  Category,
  SearchOptions
} from 'kore-memory-client';

const memories: MemoryRecord[] = await kore.search({ q: 'test' }).then(r => r.results);
```

## Categories

Available memory categories:

- `general` (default)
- `project`
- `trading`
- `finance`
- `person`
- `preference`
- `task`
- `decision`

## License

MIT © [Juan Auriti](https://github.com/auriti-web-design)

---

Part of the [Kore Memory](https://github.com/auriti-web-design/kore-memory) ecosystem.
