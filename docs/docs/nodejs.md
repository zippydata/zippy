---
layout: default
title: Node.js Guide
nav_order: 4
---

# Node.js Guide
{: .no_toc }

The Node.js SDK provides native bindings to the Rust core, giving you high performance with a familiar JavaScript API. Perfect for backend services, ETL pipelines, and serverless functions.

<details open markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
1. TOC
{:toc}
</details>

---

## Installation

```bash
npm install @zippydata/core
```

Or with yarn/pnpm:

```bash
yarn add @zippydata/core
pnpm add @zippydata/core
```

The package includes pre-built binaries for:
- **macOS**: x64 and ARM64 (Apple Silicon)
- **Linux**: x64 and ARM64
- **Windows**: x64

---

## Quick Start

```javascript
const { ZdsStore } = require('@zippydata/core');

// Create or open a store
const store = ZdsStore.open('./my_dataset', 'train');

// Add documents
store.put('user_001', { name: 'Alice', role: 'admin' });
store.put('user_002', { name: 'Bob', role: 'user' });

// Retrieve by ID
console.log(store.get('user_001'));
// { name: 'Alice', role: 'admin' }

// Iterate all documents
for (const doc of store.scan()) {
    console.log(doc._id, doc.name);
}

// Always close when done
store.close();
```

---

## Working with Stores

### Opening a Store

```javascript
const { ZdsStore } = require('@zippydata/core');

// Single collection (classic helper)
const store = ZdsStore.open('./my_data', { collection: 'train' });
store.put('doc_001', { text: 'hello' });

// Multi-collection: omit collection to get a root-capable handle
const store = ZdsStore.open('./my_data', { native: true });
const train = store.collection('train');
const evalSet = store.collection('evaluation');

train.put('doc_train', { text: 'Train sample' });
evalSet.put('doc_eval', { text: 'Eval sample' });

console.log(store.listCollections()); // ['evaluation', 'train']

// Need low-level control (lock state, mode)? Grab the underlying root
const nativeRoot = store.root; // exposes ZdsRoot / NativeRoot
// ⚠️ Closing the root tears down every reader/writer for this path.
// Only call this during shutdown/cleanup.
nativeRoot.close();
```

> 💡 Most Node.js apps can stick to `ZdsStore.open(...)`. Reach for `store.root`
> only when you need explicit read/write modes, manual locking, or to share the
> memoized root with another runtime.

### Adding Documents

Every document needs a unique string ID:

```javascript
// Simple document
store.put('product_001', {
    name: 'Widget Pro',
    price: 29.99,
    inStock: true
});

// Complex nested structure
store.put('order_001', {
    customer: {
        id: 'cust_123',
        email: 'alice@example.com'
    },
    items: [
        { sku: 'WIDGET-001', qty: 2, price: 29.99 },
        { sku: 'GADGET-002', qty: 1, price: 49.99 }
    ],
    total: 109.97,
    createdAt: new Date().toISOString()
});

// Schema-flexible: different documents can have different fields
store.put('order_002', {
    customer: { id: 'cust_456' },
    items: [{ sku: 'THING-003', qty: 5 }],
    total: 24.95,
    discount: { code: 'SAVE10', amount: 2.50 }  // New field!
});
```

### Retrieving Documents

```javascript
// Get by ID
const doc = store.get('order_001');
console.log(doc.total);  // 109.97

// Check if document exists
if (store.exists('order_001')) {
    console.log('Order found!');
}

// Get returns null for missing documents
const missing = store.get('nonexistent');
console.log(missing);  // null

// List all document IDs
const allIds = store.listDocIds();
console.log(allIds);  // ['order_001', 'order_002', ...]
```

### Updating and Deleting

```javascript
// Update (put with same ID replaces the document)
store.put('product_001', {
    name: 'Widget Pro',
    price: 24.99,      // Updated price
    inStock: true,
    onSale: true       // New field
});

// Delete
store.delete('product_001');

// Count documents
console.log(`Total documents: ${store.count}`);
```

### Scanning Documents

```javascript
// Get all documents as array
const allDocs = store.scan();
console.log(`Found ${allDocs.length} documents`);

// Iterate with for...of
for (const doc of store.scan()) {
    console.log(doc._id, doc.name);
}

// Filter in JavaScript
const admins = store.scan().filter(doc => doc.role === 'admin');
const highValue = store.scan().filter(doc => doc.total > 100);
```

### Flushing and Closing

```javascript
// Explicit flush (writes pending changes to disk)
store.flush();

// Close flushes automatically and releases resources
store.close();

// Pattern: try/finally for cleanup
const store = ZdsStore.open('./data', 'train');
try {
    // ... do work ...
} finally {
    store.close();
}
```

---

## Bulk Operations

### BulkWriter for High Throughput

When ingesting large amounts of data, use `BulkWriter` for optimal performance:

```javascript
const { BulkWriter } = require('@zippydata/core');

// Create a bulk writer with batch size of 500
const writer = BulkWriter.create('./data', 'events', 500);

// Write 100,000 documents efficiently
for (let i = 0; i < 100000; i++) {
    writer.put(`event_${i.toString().padStart(6, '0')}`, {
        timestamp: Date.now(),
        type: ['click', 'view', 'purchase'][i % 3],
        userId: `user_${i % 1000}`,
        value: Math.random() * 100
    });
}

// Final flush to write remaining documents
writer.flush();

console.log(`Wrote ${writer.count} documents`);
```

### Raw JSONL for Maximum Speed

For the absolute fastest ingestion, use raw JSONL operations:

```javascript
// Pre-serialize your data
const documents = [
    { _id: 'doc_001', text: 'Hello', score: 0.95 },
    { _id: 'doc_002', text: 'World', score: 0.87 },
    { _id: 'doc_003', text: 'Test', score: 0.72 }
];

const jsonlData = documents
    .map(doc => JSON.stringify(doc))
    .join('\n');

const docIds = documents.map(doc => doc._id);

// Write in one operation
const count = store.writeJsonl(Buffer.from(jsonlData), docIds);
console.log(`Wrote ${count} documents`);
```

### Reading Raw JSONL

```javascript
// Read entire collection as buffer (fastest for export)
const blob = store.readJsonlBlob();
console.log(`Read ${blob.length} bytes`);

// Parse manually
const lines = blob.toString().trim().split('\n');
const docs = lines.map(line => JSON.parse(line));

// Or use scanRaw for per-document buffers
const rawDocs = store.scanRaw();
for (const buf of rawDocs) {
    const doc = JSON.parse(buf.toString());
    process(doc);
}
```

---

## TypeScript

Full TypeScript definitions are included:

```typescript
import { ZdsStore, BulkWriter, StoreInfo, version } from '@zippydata/core';

// Define your document types
interface User {
    name: string;
    email: string;
    role: 'admin' | 'user' | 'guest';
    createdAt: string;
}

interface Order {
    userId: string;
    items: Array<{ sku: string; qty: number; price: number }>;
    total: number;
    status: 'pending' | 'shipped' | 'delivered';
}

// Open store
const store = ZdsStore.open('./data', 'users');

// Put with type safety
const user: User = {
    name: 'Alice',
    email: 'alice@example.com',
    role: 'admin',
    createdAt: new Date().toISOString()
};
store.put('user_001', user);

// Get and cast
const retrieved = store.get('user_001') as User | null;
if (retrieved) {
    console.log(retrieved.name);  // TypeScript knows this is a string
}

// Store info is typed
const info: StoreInfo = store.info;
console.log(`Collection: ${info.collection}, Count: ${info.count}`);

store.close();
```

---

## Recipes

### Recipe: Express API with ZDS Backend

```javascript
const express = require('express');
const { ZdsStore } = require('@zippydata/core');

const app = express();
app.use(express.json());

// Open store once at startup
const store = ZdsStore.open('./data', 'products');

// GET all products
app.get('/products', (req, res) => {
    const products = store.scan();
    res.json(products);
});

// GET single product
app.get('/products/:id', (req, res) => {
    const product = store.get(req.params.id);
    if (!product) {
        return res.status(404).json({ error: 'Not found' });
    }
    res.json(product);
});

// POST new product
app.post('/products', (req, res) => {
    const id = `prod_${Date.now()}`;
    store.put(id, { ...req.body, createdAt: new Date().toISOString() });
    store.flush();  // Ensure durability
    res.status(201).json({ id, ...req.body });
});

// DELETE product
app.delete('/products/:id', (req, res) => {
    if (!store.exists(req.params.id)) {
        return res.status(404).json({ error: 'Not found' });
    }
    store.delete(req.params.id);
    store.flush();
    res.status(204).send();
});

// Cleanup on shutdown
process.on('SIGTERM', () => {
    store.close();
    process.exit(0);
});

app.listen(3000, () => console.log('Server running on :3000'));
```

### Recipe: ETL Pipeline

```javascript
const { ZdsStore, BulkWriter } = require('@zippydata/core');
const fs = require('fs');
const readline = require('readline');

async function importFromNDJSON(inputFile, outputPath, collection) {
    const writer = BulkWriter.create(outputPath, collection, 1000);
    
    const fileStream = fs.createReadStream(inputFile);
    const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity
    });
    
    let count = 0;
    for await (const line of rl) {
        if (!line.trim()) continue;
        
        const doc = JSON.parse(line);
        const id = doc.id || doc._id || `doc_${count}`;
        
        writer.put(id, doc);
        count++;
        
        if (count % 10000 === 0) {
            console.log(`Processed ${count} documents...`);
        }
    }
    
    writer.flush();
    console.log(`Imported ${count} documents to ${outputPath}/${collection}`);
}

// Usage
importFromNDJSON('./data.ndjson', './output', 'imported');
```

### Recipe: Serverless Function (AWS Lambda)

```javascript
const { ZdsStore } = require('@zippydata/core');

// Store in /tmp for Lambda (or use EFS for persistence)
let store = null;

function getStore() {
    if (!store) {
        store = ZdsStore.open('/tmp/cache', 'data');
    }
    return store;
}

exports.handler = async (event) => {
    const s = getStore();
    
    switch (event.action) {
        case 'get':
            const doc = s.get(event.id);
            return { statusCode: doc ? 200 : 404, body: doc };
            
        case 'put':
            s.put(event.id, event.data);
            s.flush();
            return { statusCode: 201, body: { id: event.id } };
            
        case 'list':
            return { statusCode: 200, body: s.scan() };
            
        default:
            return { statusCode: 400, body: { error: 'Unknown action' } };
    }
};
```

---

## Performance Tips

### 1. Use Appropriate Batch Sizes

```javascript
// For many small writes, use larger batch size
const store = ZdsStore.open('./data', 'logs', 1000);

// For fewer large writes, smaller is fine
const store = ZdsStore.open('./data', 'reports', 50);
```

### 2. Bulk Operations for Large Datasets

```javascript
// ❌ Slow: Individual puts
for (const record of bigDataset) {
    store.put(record.id, record);
}

// ✅ Fast: BulkWriter
const writer = BulkWriter.create('./data', 'large', 500);
for (const record of bigDataset) {
    writer.put(record.id, record);
}
writer.flush();
```

### 3. Raw JSONL for Maximum Throughput

```javascript
// ✅ Fastest: Pre-serialize and write in bulk
const jsonlData = records
    .map(r => JSON.stringify({ _id: r.id, ...r }))
    .join('\n');

store.writeJsonl(Buffer.from(jsonlData), records.map(r => r.id));
```

### 4. Reuse Store Instances

```javascript
// ❌ Slow: Open/close for each operation
function getData(id) {
    const store = ZdsStore.open('./data', 'cache');
    const doc = store.get(id);
    store.close();
    return doc;
}

// ✅ Fast: Reuse store instance
const store = ZdsStore.open('./data', 'cache');

function getData(id) {
    return store.get(id);
}
```

---

## API Reference

### ZdsStore

```typescript
class ZdsStore {
    static open(path: string, collection?: string, batchSize?: number): ZdsStore;
    
    put(id: string, document: object): void;
    get(id: string): object | null;
    delete(id: string): void;
    exists(id: string): boolean;
    
    scan(): object[];
    scanRaw(): Buffer[];
    listDocIds(): string[];
    
    writeJsonl(data: Buffer, ids: string[]): number;
    readJsonlBlob(): Buffer;
    
    flush(): void;
    close(): void;
    
    readonly count: number;
    readonly info: StoreInfo;
}

interface StoreInfo {
    root: string;
    collection: string;
    count: number;
}
```

### BulkWriter

```typescript
class BulkWriter {
    static create(path: string, collection: string, batchSize?: number): BulkWriter;
    
    put(id: string, document: object): void;
    flush(): void;
    
    readonly count: number;
}
```

---

## Next Steps

- **[Getting Started](./getting-started)** — 5-minute quickstart
- **[Python Guide](./python)** — Python SDK reference
- **[CLI Reference](./cli)** — Command-line tools
- **[Examples](https://github.com/zippydata/zippy/tree/master/examples/nodejs)** — Working code samples
