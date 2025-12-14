---
layout: default
title: Documentation
nav_order: 2
has_children: true
permalink: /docs/
---

# Documentation
{: .no_toc }

Everything you need to build with ZDS—from quick starts to deep dives.

---

## Choose Your Path

<div class="features">
  <div class="feature-card">
    <div class="icon">🚀</div>
    <h3>Getting Started</h3>
    <p>Install ZDS and create your first dataset in under 5 minutes.</p>
    <a href="./getting-started" class="btn btn-primary">Start Here</a>
  </div>
  
  <div class="feature-card">
    <div class="icon">🐍</div>
    <h3>Python Guide</h3>
    <p>Full API reference with HuggingFace, Pandas, and DuckDB integrations.</p>
    <a href="./python" class="btn btn-outline">Read Guide</a>
  </div>
  
  <div class="feature-card">
    <div class="icon">📦</div>
    <h3>Node.js Guide</h3>
    <p>Native bindings for backend services, ETL pipelines, and serverless.</p>
    <a href="./nodejs" class="btn btn-outline">Read Guide</a>
  </div>
  
  <div class="feature-card">
    <div class="icon">⚙️</div>
    <h3>CLI Reference</h3>
    <p>Command-line tools for shell scripts and data pipelines.</p>
    <a href="./cli" class="btn btn-outline">View Commands</a>
  </div>
  
  <div class="feature-card">
    <div class="icon">🦀</div>
    <h3>Rust Guide</h3>
    <p>Embed the core library directly in your Rust applications.</p>
    <a href="./rust" class="btn btn-outline">Read Guide</a>
  </div>
  
  <div class="feature-card">
    <div class="icon">📐</div>
    <h3>Format Spec</h3>
    <p>Technical details of the on-disk format and index structure.</p>
    <a href="./format" class="btn btn-outline">View Spec</a>
  </div>
</div>

---

## Quick Installation

| Language | Command |
|----------|---------|
| **Python** | `pip install zippy-data` |
| **Node.js** | `npm install @zippydata/core` |
| **Rust** | `cargo add zippy_core` |
| **CLI** | [Download from releases](https://github.com/zippydata/zippy/releases) |

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

---

## Need Help?

<div class="callout info">
<strong>Resources:</strong>
<ul style="margin: 0.5rem 0 0 0;">
<li><a href="https://github.com/zippydata/zippy/issues">GitHub Issues</a> — Bug reports and feature requests</li>
<li><a href="https://github.com/zippydata/zippy/tree/master/examples">Examples</a> — Working code samples for all languages</li>
<li><a href="https://github.com/zippydata/zippy/blob/master/PAPER.md">Paper</a> — Design rationale and benchmarks</li>
</ul>
</div>
