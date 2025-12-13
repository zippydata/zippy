# @zippy/core

High-performance dataset storage for Node.js with native Rust bindings.

## Installation

```bash
npm install @zippy/core
```

## Quick Start

```typescript
import { ZDSStore, BulkWriter } from '@zippy/core';

// Open a store
const store = ZDSStore.open('./data', { collection: 'users' });

// Write documents
store.put('user_001', { name: 'Alice', age: 30 });
store.put('user_002', { name: 'Bob', age: 25 });

// Read documents
const user = store.get('user_001');
console.log(user.name); // 'Alice'

// Check existence
if (store.exists('user_001')) {
  console.log('User exists!');
}

// Iterate all documents
for (const doc of store) {
  console.log(doc);
}

// Get all document IDs
const ids = store.listDocIds();
console.log(`Found ${ids.length} documents`);

// Close and flush
store.close();
```

## High-Throughput Ingestion

For bulk writes, use the `BulkWriter` class:

```typescript
import { BulkWriter } from '@zippy/core';

const writer = BulkWriter.create('./data', {
  collection: 'events',
  batchSize: 5000
});

// Write 100k records
for (let i = 0; i < 100000; i++) {
  writer.put(`event_${i}`, {
    timestamp: Date.now(),
    value: Math.random()
  });
}

writer.flush();
console.log(`Wrote ${writer.count} documents`);
```

## API Reference

### ZDSStore

```typescript
class ZDSStore {
  static open(root: string, options?: OpenOptions): ZDSStore;
  
  get(docId: string): Document;
  getOrNull(docId: string): Document | undefined;
  put(docId: string, doc: Document): void;
  delete(docId: string): void;
  exists(docId: string): boolean;
  flush(): void;
  close(): void;
  
  scan(): Document[];
  listDocIds(): string[];
  getAt(index: number): Document;
  
  readonly count: number;
  readonly info: StoreInfo;
}

interface OpenOptions {
  collection?: string;  // Default: "default"
  batchSize?: number;   // Default: 1000
}
```

### BulkWriter

```typescript
class BulkWriter {
  static create(root: string, options?: BulkWriteOptions): BulkWriter;
  
  put(docId: string, doc: Document): void;
  flush(): void;
  
  readonly count: number;
}

interface BulkWriteOptions {
  collection?: string;  // Default: "default"
  batchSize?: number;   // Default: 5000
}
```

## Performance

Benchmarks on Apple M3 Max (10k records):

| Operation | Throughput |
|-----------|------------|
| Write | 300k+ rec/s |
| Read All | 500k+ rec/s |
| Random Access | 50k+ rec/s |

## Building from Source

```bash
cd nodejs
npm install
npm run build
```

Requires:
- Node.js 16+
- Rust 1.70+

## License

MIT
