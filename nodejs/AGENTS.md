# nodejs/AGENTS.md

Consumer guide for the **Zippy Data System Node.js SDK** (`@zippydata/core`). Use this to embed ZDS stores inside Node.js/TypeScript services, ETL jobs, or CLI tools.

## Install

```bash
npm install @zippydata/core

# TypeScript projects
npm install --save-dev typescript @types/node
```

Works on Node.js 18+ (tested on 20). Prebuilt native binaries ship for major platforms.

## Quick Start

```ts
import { ZdsStore } from '@zippydata/core';

const store = ZdsStore.open('./data', 'train');
store.put('doc_001', { text: 'hello', label: 1 });

console.log(store.get('doc_001'));
console.log(store.count);

for (const doc of store.scan()) {
  // process docs
}

store.close();
```

### Common Operations

| Need | How |
|------|-----|
| High-throughput ingestion | Use `BulkWriter.create(path, collection, batchSize)` and call `writer.put(...)` |
| List IDs | `store.listDocIds()` |
| Raw JSONL export | `const blob = store.readJsonlBlob()` |
| Random access by index | `store.getAt(idx)` |
| Streaming ingest pipeline | Pipe JSONL lines → parse → `store.put(id, doc)` |

## Typical Workflow

1. **Open a store** with `ZdsStore.open(rootPath, collection, batchSize?)`.
2. **Write data** via `put`, `writeJsonl`, or the `BulkWriter` helper.
3. **Expose APIs** using `store.get`, `store.scan`, or `store.info`.
4. **Export/share** data using the CLI (`zippy pack`) or by uploading the directory.

## Integration Recipes

| Scenario | Example |
|----------|---------|
| Express API | Open store at startup, respond with `store.get(req.params.id)` |
| Worker/cron job | Use `BulkWriter` to append processed events |
| ETL pipeline | Combine with `stream.Transform` to convert upstream JSON into `store.put` calls |
| Interop with Python | Let Node write the store; Python’s `zippy-data` package can read the same files |

## Options & Environment

* `ZdsStore.open(path, collection, batchSize = 1000)` – larger batch sizes reduce fsyncs.
* `store.flush()` – call before handing off to another process.
* Env variables:
  * `ZDS_NODE_LOG=debug` – verbose native logging
  * `RUST_LOG=zippy_data=debug` – deeper tracing during debugging

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Error: Failed to load native module` | Ensure you’re running on a supported platform/Node version; reinstall `@zippydata/core`. |
| High CPU when scanning | Reuse the same store instance and avoid JSON.parse on every request; cache derived views. |
| Batch writes not flushed | Call `writer.flush()` or pass a smaller `batchSize`. |
| Need Windows binary | Package includes msvc builds; ensure you’re not running under WSL without glibc support. |

## References

* API guide: [`docs/docs/nodejs.md`](../docs/docs/nodejs.md)
* Examples: `examples/nodejs/`
* Format spec: [`docs/docs/format.md`](../docs/docs/format.md)
* CLI companion: `npx zippy scan ./data -c train --jsonl`
