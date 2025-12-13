---
layout: default
title: Documentation
nav_order: 2
has_children: true
permalink: /docs/
---

# Documentation

Welcome to the ZDS documentation. Here you'll find everything you need to use ZDS effectively.

## Quick Links

- **[Getting Started](./getting-started)** - Install ZDS and create your first dataset
- **[Python Guide](./python)** - Full Python API with examples
- **[Node.js Guide](./nodejs)** - JavaScript/TypeScript usage
- **[Rust Guide](./rust)** - Using the core library directly
- **[CLI Reference](./cli)** - Command-line tool documentation
- **[Format Specification](./format)** - Technical format details
- **[Benchmarks](./benchmarks)** - Performance comparisons

## Installation

### Python

```bash
pip install zippy-data
```

### Node.js

```bash
npm install @zippydata/core
```

### Rust

```toml
# Cargo.toml
[dependencies]
zippy_core = "0.1"
```

### CLI

```bash
# From source
cargo install --path cli

# Or download from releases
# https://github.com/zippydata/zippy/releases
```

## Core Concepts

### Stores and Collections

A **store** is a directory (or ZIP archive) containing one or more **collections**. Each collection holds documents.

```
my_dataset/                    # Store
└── collections/
    ├── train/                 # Collection
    │   └── meta/data.jsonl   # Documents
    └── test/                  # Collection
        └── meta/data.jsonl   # Documents
```

### Documents

Documents are JSON objects with a unique `_id`:

```json
{"_id": "doc_001", "text": "Hello world", "label": 1}
{"_id": "doc_002", "text": "Goodbye", "nested": {"deep": "value"}}
```

Schema is per-document—each document can have different fields.

### Storage Modes

| Mode | Files | Best For |
|------|-------|----------|
| **JSONL** | `meta/data.jsonl` | Performance, streaming |
| **File-per-doc** | `docs/*.json` | Git diffs, manual editing |

### Indexes

ZDS uses a binary index (`index.bin`) for O(1) lookups by document ID. The index is optional—without it, operations fall back to sequential scan.

## API Overview

All language bindings share the same core operations:

| Operation | Python | Node.js | Rust | CLI |
|-----------|--------|---------|------|-----|
| Open/create | `ZDSStore.open()` | `ZdsStore.open()` | `FastStore::open()` | `zippy init` |
| Put | `store.put(id, doc)` | `store.put(id, doc)` | `store.put(id, doc)` | `zippy put` |
| Get | `store.get(id)` | `store.get(id)` | `store.get(id)` | `zippy get` |
| Delete | `store.delete(id)` | `store.delete(id)` | `store.delete(id)` | `zippy delete` |
| Scan | `store.scan()` | `store.scan()` | `store.scan_all()` | `zippy scan` |
| Count | `len(store)` | `store.count` | `store.len()` | `zippy stats` |

## HuggingFace Compatibility

ZDS provides a `ZDataset` class that mirrors the HuggingFace Dataset API:

```python
from zippy import ZDataset

dataset = ZDataset.from_store("./data", collection="train")

# HuggingFace-style operations
shuffled = dataset.shuffle(seed=42)
filtered = dataset.filter(lambda x: x["label"] == 1)
batches = dataset.batch(32)

# Convert to/from HuggingFace
from zippy import from_hf, to_hf
zds = from_hf(hf_dataset, "./output")
hf = to_hf(zds)
```

## DuckDB Integration

Query ZDS collections with SQL:

```python
from zippy import query_zds

results = query_zds(
    "./data",
    "SELECT label, COUNT(*) FROM train GROUP BY label"
)
print(results)
```

## Need Help?

- [GitHub Issues](https://github.com/zippydata/zippy/issues) - Bug reports and feature requests
- [Examples](https://github.com/zippydata/zippy/tree/main/examples) - Working code samples
- [Paper](https://github.com/zippydata/zippy/blob/main/PAPER.md) - Design rationale and benchmarks
