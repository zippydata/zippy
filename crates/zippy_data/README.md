# zippy_data

Core Rust engine for the Zippy Data System (ZDS) — a high-performance, multi-language dataset storage format. The crate powers the Python, Node.js, and CLI bindings and is optimized for fast ingestion and random access over JSONL-style datasets.

## Features

- **Fast ingestion**: Append JSON documents via `FastStore` with mmap-backed indexing
- **Random + sequential access**: Use the `Engine` API to fetch docs by id or scan with predicates/projections
- **Pack/Unpack**: Turn a store into a portable `.zds` archive (and back) with `zippy_data::container`
- **Schema/index helpers**: Manage schema registry, layout helpers, and journaled transaction log
- **Zero-copy friendly**: Uses SIMD JSON parsing and memory-mapped files for throughput

## Install

```bash
cargo add zippy_data
# optional helpers
cargo add serde_json
```

Requires Rust 1.75+.

## Example

```rust
use serde_json::json;
use zippy_data::{FastStore, Result};

fn main() -> Result<()> {
    let mut store = FastStore::open("./data", "train", 1000)?;
    store.put("doc_001", json!({"text": "hello", "label": 1}))?;
    store.flush()?;

    let doc = store.get("doc_001")?;
    println!("{}", doc["text"]);
    Ok(())
}
```

See [`AGENTS.md`](AGENTS.md) for a deeper guide, patterns, and troubleshooting tips.
