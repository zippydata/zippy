---
layout: default
title: Rust Guide
parent: Documentation
nav_order: 4
---

# Rust Guide

Using the ZDS core library directly in Rust applications.

## Installation

```toml
# Cargo.toml
[dependencies]
zippy_core = "0.1"
serde_json = "1.0"
```

## Quick Reference

```rust
use zippy_core::{FastStore, Engine, Layout, Result};
use serde_json::json;
```

---

## FastStore

High-performance JSONL-based store with mmap and binary index.

### Opening a Store

```rust
use zippy_core::{FastStore, Layout};

// Create directory structure
Layout::init_root(&path)?;

// Open store (creates collection if needed)
let mut store = FastStore::open(
    "./my_data",    // Root path
    "train",        // Collection name
    100,            // Batch size for auto-flush
)?;
```

### CRUD Operations

```rust
use serde_json::json;

// Put
store.put("doc_001", json!({
    "text": "Hello world",
    "label": 1,
    "tags": ["greeting"]
}))?;

// Get
let doc = store.get("doc_001")?;
println!("{}", doc["text"]);  // "Hello world"

// Check existence
if store.exists("doc_001") {
    println!("Found!");
}

// Delete
store.delete("doc_001")?;

// Count
println!("Documents: {}", store.len());

// List IDs
let ids = store.doc_ids();
```

### Scanning

```rust
// Scan all documents
let docs = store.scan_all()?;
for doc in docs {
    println!("{}", doc);
}

// Read raw JSONL blob (fastest)
let blob = store.read_jsonl_blob()?;
println!("Read {} bytes", blob.len());
```

### Flushing

```rust
// Explicit flush
store.flush()?;

// Refresh mmap after external changes
store.refresh_mmap()?;
```

---

## Engine

File-per-document store with the Engine API.

### Opening

```rust
use zippy_core::Engine;

let engine = Engine::open("./data", "train")?;
```

### Reading

```rust
// Get by ID
let doc = engine.get_document("doc_001")?;

// Get by index position
let first = engine.get_document_at(0)?;

// Count
println!("Documents: {}", engine.len());

// List IDs
let ids = engine.doc_ids();
```

### Scanning with Predicates

```rust
use zippy_core::Predicate;

// Scan all
let mut scanner = engine.scan(None, None)?;
while let Some(doc) = scanner.next()? {
    println!("{}", doc);
}

// With predicate
let pred = Predicate::eq("category", "electronics");
let mut scanner = engine.scan(Some(&pred), None)?;

// With projection
let fields = ["name", "price"];
let mut scanner = engine.scan(None, Some(&fields))?;

// Combined
let mut scanner = engine.scan(Some(&pred), Some(&fields))?;

// Collect all
let docs: Vec<_> = scanner.collect();
```

### Statistics

```rust
let stats = engine.stats();
println!("Collection: {}", stats.collection);
println!("Documents: {}", stats.doc_count);
println!("Schemas: {}", stats.schema_count);
println!("Total size: {} bytes", stats.total_size);
println!("Strict mode: {}", stats.strict_mode);
```

---

## Writers

### SyncWriter

Synchronous file-per-document writes.

```rust
use zippy_core::writer::SyncWriter;

let mut writer = SyncWriter::new("./data", "train")?;

writer.put("doc_001", &json!({"text": "hello"}))?;
writer.put("doc_002", &json!({"text": "world"}))?;

// Changes are written immediately
```

### BufferedWriter

Batched writes for better performance.

```rust
use zippy_core::writer::{BufferedWriter, WriteConfig};

let config = WriteConfig {
    max_pending_ops: 1000,
    max_pending_bytes: 100 * 1024 * 1024,  // 100MB
    flush_interval_ms: 60000,
};

let mut writer = BufferedWriter::new("./data", "train", config)?;

for i in 0..10000 {
    writer.put(format!("doc_{:06}", i), json!({"id": i}))?;
}

// Explicit flush
writer.flush()?;
```

---

## Pack/Unpack

Create and extract .zds archives.

```rust
use zippy_core::container::{pack, unpack};

// Pack directory to archive
pack("./my_dataset", "./my_dataset.zds")?;

// Unpack archive to directory
unpack("./my_dataset.zds", "./extracted")?;
```

---

## Index Operations

### Rebuild Index

```rust
use zippy_core::IndexRegistry;

let index = IndexRegistry::rebuild("./data", "train")?;
index.save("./data", "train")?;
println!("Indexed {} documents", index.len());
```

### Load Index

```rust
let index = IndexRegistry::load("./data", "train")?;
println!("Loaded {} entries", index.len());

// Get document ID at position
if let Some(id) = index.get_doc_id_at(0) {
    println!("First ID: {}", id);
}
```

---

## Layout Utilities

```rust
use zippy_core::Layout;

// Initialize store structure
Layout::init_root("./data")?;

// Initialize collection
Layout::init_collection("./data", "train")?;

// Validate structure
Layout::validate("./data")?;
Layout::validate_collection("./data", "train")?;

// Get paths
let meta_dir = Layout::meta_dir("./data", "train");
let manifest = Layout::manifest_file("./data", "train");
```

---

## Error Handling

```rust
use zippy_core::{Error, Result};

fn process() -> Result<()> {
    let store = FastStore::open("./data", "train", 100)?;
    
    match store.get("nonexistent") {
        Ok(doc) => println!("{}", doc),
        Err(Error::DocumentNotFound(id)) => {
            println!("Not found: {}", id);
        }
        Err(e) => return Err(e),
    }
    
    Ok(())
}
```

---

## Benchmarking

Run the built-in benchmarks:

```bash
cd crates/zippy_core
cargo bench
```

### Available Benchmarks

| Suite | Description |
|-------|-------------|
| `ingestion` | Write throughput |
| `random_access` | Lookup performance |
| `scan` | Sequential read speed |

---

## Examples

See the [examples directory](https://github.com/zippydata/zippy/tree/main/examples/rust):

- `basic_usage.rs` - Core operations
- `streaming_data.rs` - Bulk ingestion
- `ml_dataset.rs` - ML workflows

### Run Examples

```bash
cd examples/rust
cargo run --bin basic_usage
cargo run --bin streaming_data
cargo run --bin ml_dataset
```

---

## Performance Notes

### FastStore vs Engine

| Feature | FastStore | Engine |
|---------|-----------|--------|
| Storage | JSONL | File-per-doc |
| Write speed | Faster | Slower |
| Random read | O(1) mmap | O(1) file read |
| Best for | Bulk ops | Git-friendly |

### Optimization Tips

1. **Use FastStore for bulk operations**
2. **Set appropriate batch size** (100-1000)
3. **Call flush() before reads** to ensure consistency
4. **Use scan_all() over individual gets** for bulk reads
5. **Pre-allocate buffers** when writing large datasets
