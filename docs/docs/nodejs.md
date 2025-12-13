---
layout: default
title: Node.js Guide
parent: Documentation
nav_order: 3
---

# Node.js Guide

Complete guide to using ZDS with Node.js and TypeScript.

## Installation

```bash
npm install @zippydata/core
```

## Quick Reference

```typescript
import { ZdsStore, BulkWriter, version } from '@zippydata/core';

// Check version
console.log(version());  // "0.1.0"
```

---

## ZdsStore

The primary interface for document operations.

### Opening a Store

```javascript
const { ZdsStore } = require('@zippydata/core');

// Open or create
const store = ZdsStore.open(
    './my_data',    // Root path
    'train',        // Collection name (optional, default: "default")
    100             // Batch size for auto-flush (optional)
);

// Always close when done
store.close();
```

### CRUD Operations

```javascript
// Put (create or update)
store.put('doc_001', { text: 'Hello', label: 1 });
store.put('doc_002', { text: 'World', tags: ['a', 'b'] });

// Get by ID
const doc = store.get('doc_001');
console.log(doc);  // { text: 'Hello', label: 1 }

// Check existence
if (store.exists('doc_001')) {
    console.log('Found!');
}

// Delete
store.delete('doc_002');

// Count
console.log(store.count);  // Number of documents

// List all IDs
const ids = store.listDocIds();
console.log(ids);  // ['doc_001', ...]
```

### Scanning

```javascript
// Scan all documents
const docs = store.scan();
for (const doc of docs) {
    console.log(doc);
}

// Scan returns an array
console.log(`Total: ${docs.length}`);
```

### Flushing

```javascript
// Explicit flush (writes pending changes to disk)
store.flush();

// Close also flushes
store.close();
```

### Store Info

```javascript
const info = store.info;
console.log(info);
// {
//   root: '/path/to/data',
//   collection: 'train',
//   count: 1000
// }
```

---

## BulkWriter

High-throughput writer for bulk ingestion.

```javascript
const { BulkWriter } = require('@zippydata/core');

// Create writer
const writer = BulkWriter.create(
    './data',       // Root path
    'large',        // Collection
    500             // Batch size (auto-flush threshold)
);

// Write many documents
for (let i = 0; i < 100000; i++) {
    writer.put(`doc_${i}`, {
        id: i,
        value: Math.random(),
        category: ['A', 'B', 'C'][i % 3]
    });
}

// Final flush
writer.flush();

console.log(`Wrote ${writer.count} documents`);
```

---

## Raw JSONL Operations

For maximum performance, use raw JSONL methods.

### Write JSONL Blob

```javascript
// Pre-serialize your data
const lines = [
    JSON.stringify({ _id: 'doc_1', text: 'hello' }),
    JSON.stringify({ _id: 'doc_2', text: 'world' })
].join('\n');

const buffer = Buffer.from(lines);
const docIds = ['doc_1', 'doc_2'];

const count = store.writeJsonl(buffer, docIds);
console.log(`Wrote ${count} documents`);
```

### Read JSONL Blob

```javascript
// Read entire file as buffer (fastest)
const blob = store.readJsonlBlob();
console.log(`Read ${blob.length} bytes`);

// Parse manually
const lines = blob.toString().trim().split('\n');
const docs = lines.map(line => JSON.parse(line));
```

### Scan Raw

```javascript
// Get array of Buffer (one per document)
const rawDocs = store.scanRaw();
for (const buf of rawDocs) {
    const doc = JSON.parse(buf.toString());
    process(doc);
}
```

---

## TypeScript

Full TypeScript definitions are included.

```typescript
import { ZdsStore, BulkWriter, StoreInfo, version } from '@zippydata/core';

interface MyDocument {
    text: string;
    label: number;
    tags?: string[];
}

const store = ZdsStore.open('./data', 'train');

// Put with type
store.put('doc_001', {
    text: 'Hello',
    label: 1,
    tags: ['greeting']
} as MyDocument);

// Get returns any (parse as needed)
const doc = store.get('doc_001') as MyDocument;
console.log(doc.text);

// Store info is typed
const info: StoreInfo = store.info;
console.log(info.count);

store.close();
```

---

## Error Handling

```javascript
const { ZdsStore } = require('@zippydata/core');

try {
    const store = ZdsStore.open('./data', 'train');
    
    // Document not found
    try {
        const doc = store.get('nonexistent');
    } catch (e) {
        console.log('Document not found');
    }
    
    store.close();
} catch (e) {
    console.error('Store error:', e.message);
}
```

---

## Performance Tips

### Batch Size

```javascript
// Higher batch size = fewer disk writes = faster
const store = ZdsStore.open('./data', 'train', 1000);
```

### Use BulkWriter for Large Ingestion

```javascript
// BulkWriter is optimized for sequential writes
const writer = BulkWriter.create('./data', 'large', 500);

// Much faster than individual puts
for (const record of bigDataset) {
    writer.put(record.id, record);
}
writer.flush();
```

### Raw JSONL for Maximum Speed

```javascript
// Pre-serialize for bulk operations
const jsonlData = records
    .map(r => JSON.stringify({ _id: r.id, ...r }))
    .join('\n');

store.writeJsonl(Buffer.from(jsonlData), records.map(r => r.id));
```

---

## Examples

See the [examples directory](https://github.com/zippydata/zippy/tree/main/examples/nodejs):

- `01_basic_usage.js` - Core operations
- `02_streaming_data.js` - Bulk and streaming

### Basic Example

```javascript
const { ZdsStore, version } = require('@zippydata/core');
const fs = require('fs');

console.log(`ZDS Version: ${version()}`);

// Create store
const store = ZdsStore.open('./example_data', 'demo');

// Add documents
const users = [
    { name: 'Alice', role: 'admin' },
    { name: 'Bob', role: 'user' },
    { name: 'Charlie', role: 'user' }
];

users.forEach((user, i) => {
    store.put(`user_${i}`, user);
});

console.log(`Created ${store.count} users`);

// Query
const docs = store.scan();
const admins = docs.filter(d => d.role === 'admin');
console.log(`Admins: ${admins.length}`);

// Cleanup
store.close();
```
