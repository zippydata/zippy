---
layout: default
title: Rust Guide
nav_order: 5
---

# Rust Guide
{: .no_toc }

The Rust crate `zippy_core` is the foundation of ZDS. It provides zero-copy memory-mapped access, high-throughput writers, and full control over the storage layer. Use it when you need maximum performance or want to embed ZDS in your Rust application.

<details open markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
1. TOC
{:toc}
</details>

---

## Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
zippy_core = "0.1"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
```

For async support:

```toml
[dependencies]
zippy_core = { version = "0.1", features = ["async"] }
tokio = { version = "1", features = ["full"] }
```

---

## Quick Start

```rust
use zippy_core::{FastStore, Layout, Result};
use serde_json::json;

fn main() -> Result<()> {
    // Initialize the store directory
    Layout::init_root("./my_dataset")?;
    
    // Open a collection (creates if doesn't exist)
    let mut store = FastStore::open("./my_dataset", "train", 100)?;
    
    // Add documents
    store.put("user_001", json!({
        "name": "Alice",
        "email": "alice@example.com",
        "role": "admin"
    }))?;
    
    store.put("user_002", json!({
        "name": "Bob",
        "email": "bob@example.com",
        "role": "user"
    }))?;
    
    // Retrieve by ID
    let doc = store.get("user_001")?;
    println!("Found: {}", doc["name"]);  // "Alice"
    
    // Iterate all documents
    for doc in store.scan_all()? {
        println!("{}: {}", doc["_id"], doc["name"]);
    }
    
    // Flush to ensure durability
    store.flush()?;
    
    println!("Stored {} documents", store.len());
    Ok(())
}
```

---

## Core Concepts

### Store Types

ZDS provides two storage backends:

| Type | Storage | Best For |
|------|---------|----------|
| **FastStore** | Single JSONL file + binary index | High throughput, bulk operations |
| **Engine** | One JSON file per document | Git-friendly, manual editing |

### Memory-Mapped I/O

`FastStore` uses memory-mapped files for zero-copy reads. The binary index provides O(1) lookups by document ID without loading the entire dataset into memory.

### Batch Writes

Both stores support batched writes. Documents are buffered in memory and flushed to disk when the batch size is reached or when `flush()` is called explicitly.

---

## FastStore

The primary high-performance store for most use cases.

### Opening a Store

```rust
use zippy_core::{FastStore, Layout};

// First-time setup: create directory structure
Layout::init_root("./data")?;

// Open with default batch size (100)
let mut store = FastStore::open("./data", "train", 100)?;

// Check store info
println!("Path: {}", store.root());
println!("Collection: {}", store.collection());
println!("Documents: {}", store.len());
```

### Adding Documents

```rust
use serde_json::json;

// Simple document
store.put("product_001", json!({
    "name": "Widget Pro",
    "price": 29.99,
    "in_stock": true
}))?;

// Nested structures
store.put("order_001", json!({
    "customer": {
        "id": "cust_123",
        "email": "alice@example.com"
    },
    "items": [
        {"sku": "WIDGET-001", "qty": 2, "price": 29.99},
        {"sku": "GADGET-002", "qty": 1, "price": 49.99}
    ],
    "total": 109.97
}))?;

// With typed structs
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
struct User {
    name: String,
    email: String,
    role: String,
}

let user = User {
    name: "Charlie".into(),
    email: "charlie@example.com".into(),
    role: "user".into(),
};

store.put("user_003", serde_json::to_value(&user)?)?;
```

### Retrieving Documents

```rust
// Get by ID (returns serde_json::Value)
let doc = store.get("order_001")?;
println!("Total: {}", doc["total"]);

// Check existence without loading
if store.exists("order_001") {
    println!("Order exists!");
}

// Get all document IDs
let ids = store.doc_ids();
for id in ids {
    println!("ID: {}", id);
}

// Deserialize to typed struct
let user: User = serde_json::from_value(store.get("user_003")?)?;
println!("User: {}", user.name);
```

### Updating and Deleting

```rust
// Update (put with same ID replaces)
store.put("product_001", json!({
    "name": "Widget Pro",
    "price": 24.99,  // Updated price
    "in_stock": true,
    "on_sale": true  // New field
}))?;

// Delete
store.delete("product_001")?;

// Verify deletion
assert!(!store.exists("product_001"));
```

### Scanning Documents

```rust
// Scan all documents
let docs = store.scan_all()?;
for doc in docs {
    println!("{}", doc);
}

// Read raw JSONL (fastest for export)
let blob = store.read_jsonl_blob()?;
println!("Read {} bytes", blob.len());

// Write to file
std::fs::write("export.jsonl", &blob)?;
```

### Flushing and Consistency

```rust
// Explicit flush writes pending changes to disk
store.flush()?;

// After external modifications, refresh the mmap
store.refresh_mmap()?;

// Drop flushes automatically
drop(store);
```

---

## Engine (File-per-Document)

For workflows that benefit from individual files per document.

### Opening

```rust
use zippy_core::Engine;

let engine = Engine::open("./data", "train")?;
println!("Documents: {}", engine.len());
```

### Reading Documents

```rust
// Get by ID
let doc = engine.get_document("doc_001")?;

// Get by index position (0-based)
let first = engine.get_document_at(0)?;
let last = engine.get_document_at(engine.len() - 1)?;

// List all IDs
for id in engine.doc_ids() {
    println!("{}", id);
}
```

### Scanning with Filters

```rust
use zippy_core::Predicate;

// Scan all documents
let mut scanner = engine.scan(None, None)?;
while let Some(doc) = scanner.next()? {
    println!("{}", doc);
}

// Filter with predicate
let pred = Predicate::eq("category", "electronics");
let mut scanner = engine.scan(Some(&pred), None)?;

// Project specific fields only
let fields = ["name", "price"];
let mut scanner = engine.scan(None, Some(&fields))?;

// Combine filter and projection
let mut scanner = engine.scan(Some(&pred), Some(&fields))?;

// Collect into Vec
let docs: Vec<_> = scanner.collect();
println!("Found {} matching documents", docs.len());
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

Immediate writes for small datasets or when durability per-write is required:

```rust
use zippy_core::writer::SyncWriter;
use serde_json::json;

let mut writer = SyncWriter::new("./data", "train")?;

// Each put writes immediately to disk
writer.put("doc_001", &json!({"text": "hello"}))?;
writer.put("doc_002", &json!({"text": "world"}))?;
```

### BufferedWriter

High-throughput batched writes:

```rust
use zippy_core::writer::{BufferedWriter, WriteConfig};
use serde_json::json;

let config = WriteConfig {
    max_pending_ops: 1000,           // Flush after 1000 documents
    max_pending_bytes: 100 << 20,    // Or after 100MB
    flush_interval_ms: 60_000,       // Or after 60 seconds
};

let mut writer = BufferedWriter::new("./data", "train", config)?;

// Bulk ingestion
for i in 0..100_000 {
    writer.put(
        format!("doc_{:06}", i),
        json!({
            "id": i,
            "value": rand::random::<f64>(),
            "category": ["A", "B", "C"][i % 3]
        })
    )?;
}

// Final flush
writer.flush()?;
println!("Wrote {} documents", writer.count());
```

---

## Recipes

### Recipe: ML Dataset Ingestion

```rust
use zippy_core::{FastStore, Layout, Result};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::fs::File;
use std::io::{BufRead, BufReader};

#[derive(Deserialize)]
struct RawSample {
    text: String,
    label: i32,
}

fn ingest_dataset(input_path: &str, output_path: &str) -> Result<()> {
    Layout::init_root(output_path)?;
    let mut store = FastStore::open(output_path, "train", 500)?;
    
    let file = File::open(input_path)?;
    let reader = BufReader::new(file);
    
    for (i, line) in reader.lines().enumerate() {
        let line = line?;
        let sample: RawSample = serde_json::from_str(&line)?;
        
        store.put(
            format!("sample_{:08}", i),
            json!({
                "text": sample.text,
                "label": sample.label,
                "split": "train"
            })
        )?;
        
        if i % 10_000 == 0 {
            println!("Processed {} samples...", i);
        }
    }
    
    store.flush()?;
    println!("Ingested {} samples", store.len());
    Ok(())
}
```

### Recipe: Parallel Processing

```rust
use zippy_core::{FastStore, Result};
use rayon::prelude::*;
use serde_json::Value;

fn process_in_parallel(store_path: &str) -> Result<Vec<Value>> {
    let store = FastStore::open(store_path, "train", 100)?;
    
    // Get all document IDs
    let ids: Vec<String> = store.doc_ids().into_iter().collect();
    
    // Process in parallel with rayon
    let results: Vec<Value> = ids
        .par_iter()
        .filter_map(|id| {
            // Each thread opens its own store handle
            let local_store = FastStore::open(store_path, "train", 100).ok()?;
            let doc = local_store.get(id).ok()?;
            
            // Your processing logic here
            if doc["score"].as_f64()? > 0.8 {
                Some(doc)
            } else {
                None
            }
        })
        .collect();
    
    Ok(results)
}
```

### Recipe: Streaming Export

```rust
use zippy_core::{FastStore, Result};
use std::io::{Write, BufWriter};
use std::fs::File;

fn export_to_jsonl(store_path: &str, output_path: &str) -> Result<()> {
    let store = FastStore::open(store_path, "train", 100)?;
    
    let file = File::create(output_path)?;
    let mut writer = BufWriter::new(file);
    
    for doc in store.scan_all()? {
        serde_json::to_writer(&mut writer, &doc)?;
        writeln!(writer)?;
    }
    
    writer.flush()?;
    println!("Exported {} documents to {}", store.len(), output_path);
    Ok(())
}
```

### Recipe: Custom Serialization

```rust
use zippy_core::{FastStore, Layout, Result};
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize, Debug)]
struct Embedding {
    id: String,
    vector: Vec<f32>,
    metadata: EmbeddingMeta,
}

#[derive(Serialize, Deserialize, Debug)]
struct EmbeddingMeta {
    source: String,
    model: String,
    timestamp: i64,
}

fn store_embeddings(embeddings: Vec<Embedding>, path: &str) -> Result<()> {
    Layout::init_root(path)?;
    let mut store = FastStore::open(path, "embeddings", 100)?;
    
    for emb in embeddings {
        store.put(&emb.id, serde_json::to_value(&emb)?)?;
    }
    
    store.flush()?;
    Ok(())
}

fn load_embedding(path: &str, id: &str) -> Result<Embedding> {
    let store = FastStore::open(path, "embeddings", 100)?;
    let value = store.get(id)?;
    let emb: Embedding = serde_json::from_value(value)?;
    Ok(emb)
}
```

---

## Pack/Unpack Archives

Create portable `.zds` archives:

```rust
use zippy_core::container::{pack, unpack};

// Pack a store directory into a single archive
pack("./my_dataset", "./my_dataset.zds")?;

// Unpack an archive
unpack("./my_dataset.zds", "./extracted")?;

// The archive is a standard ZIP file
// Recipients can extract with any ZIP tool
```

---

## Index Operations

### Rebuild Index

```rust
use zippy_core::IndexRegistry;

// Rebuild from JSONL data
let index = IndexRegistry::rebuild("./data", "train")?;
index.save("./data", "train")?;
println!("Indexed {} documents", index.len());
```

### Load and Query Index

```rust
let index = IndexRegistry::load("./data", "train")?;

// Get document ID at position
if let Some(id) = index.get_doc_id_at(0) {
    println!("First document: {}", id);
}

// Check if ID exists
if index.contains("doc_001") {
    println!("Document exists in index");
}
```

---

## Layout Utilities

```rust
use zippy_core::Layout;

// Initialize store structure
Layout::init_root("./data")?;

// Initialize a collection
Layout::init_collection("./data", "train")?;

// Validate structure
Layout::validate("./data")?;
Layout::validate_collection("./data", "train")?;

// Get paths
let meta_dir = Layout::meta_dir("./data", "train");
let manifest = Layout::manifest_file("./data", "train");
let data_file = Layout::data_file("./data", "train");
```

---

## Error Handling

```rust
use zippy_core::{Error, Result};

fn safe_get(store: &FastStore, id: &str) -> Result<Option<serde_json::Value>> {
    match store.get(id) {
        Ok(doc) => Ok(Some(doc)),
        Err(Error::DocumentNotFound(_)) => Ok(None),
        Err(e) => Err(e),
    }
}

fn process() -> Result<()> {
    let store = FastStore::open("./data", "train", 100)?;
    
    match safe_get(&store, "maybe_exists")? {
        Some(doc) => println!("Found: {}", doc),
        None => println!("Not found"),
    }
    
    Ok(())
}
```

### Error Types

| Error | Description |
|-------|-------------|
| `Error::DocumentNotFound(id)` | Document with given ID doesn't exist |
| `Error::CollectionNotFound(name)` | Collection doesn't exist |
| `Error::InvalidPath(path)` | Path is invalid or inaccessible |
| `Error::CorruptedIndex` | Binary index is corrupted |
| `Error::IoError(e)` | Underlying I/O error |
| `Error::JsonError(e)` | JSON serialization/deserialization error |

---

## Performance Tips

### 1. Choose the Right Store

| Use Case | Recommended |
|----------|-------------|
| Bulk ingestion | `FastStore` with `BufferedWriter` |
| Random access reads | `FastStore` (mmap) |
| Git-versioned data | `Engine` (file-per-doc) |
| Streaming large datasets | `FastStore` + `scan_all()` |

### 2. Tune Batch Size

```rust
// Small documents, high throughput: larger batch
let store = FastStore::open("./data", "logs", 1000)?;

// Large documents: smaller batch
let store = FastStore::open("./data", "embeddings", 50)?;
```

### 3. Use Raw JSONL for Bulk Operations

```rust
// Fastest: read raw bytes
let blob = store.read_jsonl_blob()?;

// Process line by line without full parse
for line in blob.split(|&b| b == b'\n') {
    if !line.is_empty() {
        // Quick field extraction with simd-json or similar
    }
}
```

### 4. Parallel Reads

```rust
use rayon::prelude::*;

let ids: Vec<_> = store.doc_ids().into_iter().collect();

// Each thread gets its own store handle
let results: Vec<_> = ids.par_iter()
    .map(|id| {
        let s = FastStore::open("./data", "train", 100).unwrap();
        s.get(id).unwrap()
    })
    .collect();
```

---

## Benchmarking

Run the built-in benchmarks:

```bash
cd crates/zippy_core
cargo bench
```

### Benchmark Suites

| Suite | Description |
|-------|-------------|
| `ingestion` | Write throughput (docs/sec) |
| `random_access` | Single document lookup latency |
| `scan` | Sequential read throughput |
| `index` | Index build and lookup performance |

### Example Results (M1 MacBook Pro)

| Operation | Throughput |
|-----------|------------|
| Sequential writes | 4.6M docs/sec |
| Random reads | 890K docs/sec |
| Full scan | 12M docs/sec |

---

## API Reference

### FastStore

```rust
impl FastStore {
    pub fn open(root: &str, collection: &str, batch_size: usize) -> Result<Self>;
    
    pub fn put(&mut self, id: &str, doc: Value) -> Result<()>;
    pub fn get(&self, id: &str) -> Result<Value>;
    pub fn delete(&mut self, id: &str) -> Result<()>;
    pub fn exists(&self, id: &str) -> bool;
    
    pub fn scan_all(&self) -> Result<Vec<Value>>;
    pub fn read_jsonl_blob(&self) -> Result<Vec<u8>>;
    pub fn doc_ids(&self) -> Vec<&str>;
    
    pub fn len(&self) -> usize;
    pub fn is_empty(&self) -> bool;
    
    pub fn flush(&mut self) -> Result<()>;
    pub fn refresh_mmap(&mut self) -> Result<()>;
    
    pub fn root(&self) -> &str;
    pub fn collection(&self) -> &str;
}
```

### BufferedWriter

```rust
impl BufferedWriter {
    pub fn new(root: &str, collection: &str, config: WriteConfig) -> Result<Self>;
    
    pub fn put(&mut self, id: String, doc: Value) -> Result<()>;
    pub fn flush(&mut self) -> Result<()>;
    pub fn count(&self) -> usize;
}

pub struct WriteConfig {
    pub max_pending_ops: usize,
    pub max_pending_bytes: usize,
    pub flush_interval_ms: u64,
}
```

---

## Next Steps

- **[Getting Started](./getting-started)** — 5-minute quickstart
- **[Python Guide](./python)** — Python SDK for data science workflows
- **[Format Specification](./format)** — On-disk structure details
- **[Benchmarks](./benchmarks)** — Detailed performance comparisons
