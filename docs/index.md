---
layout: default
title: Home
nav_order: 1
description: "ZDS - A human-readable, schema-flexible document store for modern data workflows"
permalink: /
---

<div class="callout info" style="margin-bottom: 2rem;">
<strong>Working on the codebase with AI?</strong> Start with <a href="https://github.com/zippydata/zippy/blob/master/AGENTS.md">AGENTS.md</a> for global setup and package-specific guides.
</div>

<div class="hero">
  <img src="{{ '/assets/images/zippy-logo.png' | relative_url }}" alt="Zippy Data System" class="logo">
  <h1>Zippy Data System</h1>
  <p class="tagline">
    A human-readable, schema-flexible document store built for modern ML and data engineering workflows.
    Store JSON documents with the simplicity of files and the speed of databases.
  </p>
  <div>
    <a href="{{ '/docs/getting-started' | relative_url }}" class="btn btn-primary">Get Started</a>
    <a href="https://github.com/zippydata/zippy" class="btn btn-secondary">View on GitHub</a>
  </div>
</div>

<div class="stats-banner">
  <div class="stat">
    <div class="value">20x</div>
    <div class="label">Faster Writes</div>
  </div>
  <div class="stat">
    <div class="value">3.5x</div>
    <div class="label">Faster Access</div>
  </div>
  <div class="stat">
    <div class="value">100%</div>
    <div class="label">Human-Readable</div>
  </div>
  <div class="stat">
    <div class="value">Zero</div>
    <div class="label">Lock-in</div>
  </div>
</div>

## Why ZDS?

Modern ML and data workflows need **flexibility** that traditional formats struggle to provide. Parquet and Arrow enforce rigid schemas. SQLite requires SQL. Plain JSON has no indexing. ZDS bridges this gap.

<div class="features">
  <div class="feature-card">
    <div class="icon">📄</div>
    <h3>Human-Readable</h3>
    <p>Debug with <code>cat</code>. Edit with <code>vim</code>. Version control with <code>git</code>. Your data is always accessible with standard tools.</p>
  </div>
  
  <div class="feature-card">
    <div class="icon">🔀</div>
    <h3>Schema-Flexible</h3>
    <p>Each document defines its own shape. No migrations needed. Perfect for iterative development and heterogeneous data.</p>
  </div>
  
  <div class="feature-card">
    <div class="icon">⚡</div>
    <h3>High Performance</h3>
    <p>Rust core with mmap, simd-json, and FxHashMap. O(1) random access. Writes at 4.6M records/second.</p>
  </div>
  
  <div class="feature-card">
    <div class="icon">🌐</div>
    <h3>Multi-Language</h3>
    <p>Native bindings for Python, Node.js, and Rust. Query with DuckDB SQL. One format, every platform.</p>
  </div>
  
  <div class="feature-card">
    <div class="icon">🔓</div>
    <h3>Zero Lock-in</h3>
    <p>ZIP container + JSONL documents. If this library disappears, your data remains fully accessible forever.</p>
  </div>
  
  <div class="feature-card">
    <div class="icon">🤖</div>
    <h3>ML-Ready</h3>
    <p>HuggingFace Dataset API compatible. Streaming iteration. Shuffle buffers. Built for training pipelines.</p>
  </div>
</div>

---

## Quick Start

<!-- <div class="quick-start"> -->

### Python

```bash
pip install zippy-data
```

```python
from zippy import ZDSStore, ZDSRoot, ZDataset

# Legacy helper: single-collection store (still supported)
store = ZDSStore.open("./my_dataset", collection="train")

# Add documents
store.put("doc_001", {"text": "Hello world", "label": 1})
store.put("doc_002", {"text": "Goodbye", "label": 0, "extra": [1, 2, 3]})

# Random access
print(store["doc_001"])  # {"text": "Hello world", "label": 1}

# Preferred: open a root once, then grab multiple collections
root = ZDSRoot.open("./my_dataset", native=True)
train = root.collection("train")
test = root.collection("test")

# Iterate like HuggingFace
dataset = ZDataset(train)
for doc in dataset.shuffle(seed=42):
    print(doc["text"])

print(root.list_collections())  # ['test', 'train']
```

### Node.js

```bash
npm install @zippydata/core
```

```javascript
const { ZdsStore } = require('@zippydata/core');

const store = ZdsStore.open('./my_dataset', 'train');

store.put('doc_001', { text: 'Hello world', label: 1 });
console.log(store.get('doc_001'));

for (const doc of store.scan()) {
    console.log(doc.text);
}
```

### CLI

```bash
# Initialize a store
zippy init ./my_dataset -c train

# Add documents
zippy put ./my_dataset -c train doc_001 --data '{"text": "Hello"}'

# Query
zippy scan ./my_dataset -c train --fields text,label
```

<!-- </div> -->

---

## How It Compares

<table class="comparison-table">
  <thead>
    <tr>
      <th>Feature</th>
      <th>ZDS</th>
      <th>Parquet</th>
      <th>SQLite</th>
      <th>Plain JSON</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Human-readable</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
      <td class="cross">❌</td>
      <td class="check">✅</td>
    </tr>
    <tr>
      <td>Schema-flexible</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
      <td class="partial">⚠️</td>
      <td class="check">✅</td>
    </tr>
    <tr>
      <td>Fast random access</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
    </tr>
    <tr>
      <td>Indexed lookups</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
    </tr>
    <tr>
      <td>Git-friendly</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
      <td class="cross">❌</td>
      <td class="check">✅</td>
    </tr>
    <tr>
      <td>No special tools</td>
      <td class="check">✅</td>
      <td class="cross">❌</td>
      <td class="partial">⚠️</td>
      <td class="check">✅</td>
    </tr>
    <tr>
      <td>ML dataset API</td>
      <td class="check">✅</td>
      <td class="partial">⚠️</td>
      <td class="cross">❌</td>
      <td class="cross">❌</td>
    </tr>
  </tbody>
</table>

---

## The Philosophy

> *"The best format is one you can understand in 5 minutes and debug with `cat`."*

ZDS follows proven patterns. A ZIP container wrapping human-readable JSONL documents, enhanced with binary indexes for performance. Like DOCX wraps XML, or EPUB wraps HTML.

```
my_dataset/
└── collections/
    └── train/
        ├── meta/
        │   └── data.jsonl     # Your data (one JSON per line)
        └── index.bin          # Optional: O(1) lookups
```

**This isn't meant to be novel and it's intentionally unoriginal.** Novelty in file formats creates lock-in. We chose boring technologies that will outlast any single library.

[Read the full paper →](https://github.com/zippydata/zippy/blob/master/PAPER.md)

---

## Use Cases

### Evaluation Pipelines
```
Run experiment → Generate 10,000 results
├── Each result has: metrics, predictions, metadata
├── Some results have additional debug info
├── Need to inspect failures manually
└── Want to version control changes
```

### Synthetic Data Generation
```
Generate training examples with LLM
├── Each example has variable structure  
├── Tool calls, function schemas, nested conversations
├── Need to filter, edit, regenerate subsets
└── Feed directly into training pipeline
```

### Dataset Distribution
```bash
# Pack for sharing
zippy pack ./my_dataset dataset.zds

# Recipients can inspect without any library
unzip dataset.zds -d extracted/
cat extracted/collections/train/meta/data.jsonl | head -5 | jq .
```

---

## Performance

Benchmarked on Apple M3 Max with 100,000 records:

| Operation | ZDS | SQLite | Pandas CSV | HF Datasets |
|-----------|-----|--------|------------|-------------|
| **Write** | **4.66M** rec/s | 237k | 205k | 633k |
| **Read All** (warm) | **510k** rec/s | 263k | 8.18M* | 40k |
| **Random Access** | **308k** rec/s | 88k | 227k | 30k |

*Pandas warm = in-memory DataFrame

[See full benchmarks →]({{ '/docs/benchmarks' | relative_url }})

---

## Get Started

<div class="features">
  <div class="feature-card">
    <h3>📖 Documentation</h3>
    <p>Complete API reference and guides for Python, Node.js, Rust, and CLI.</p>
    <a href="{{ '/docs/' | relative_url }}" class="btn btn-outline">Read Docs</a>
  </div>
  
  <div class="feature-card">
    <h3>🚀 Getting Started</h3>
    <p>Install ZDS and build your first dataset in under 5 minutes.</p>
    <a href="{{ '/docs/getting-started' | relative_url }}" class="btn btn-outline">Quick Start</a>
  </div>
  
  <div class="feature-card">
    <h3>📊 Examples</h3>
    <p>Real-world examples for ML training, data pipelines, and more.</p>
    <a href="https://github.com/zippydata/zippy/tree/master/examples" class="btn btn-outline">View Examples</a>
  </div>
</div>

---

<footer style="text-align: center; margin-top: 3rem; padding: 2rem 0; border-top: 1px solid #e2e8f0;">
  <p style="color: #64748b; font-size: 0.9rem; margin: 0;">
    Zippy Data System is open source under the MIT License<br>
    <span style="margin-top: 0.5rem; display: inline-block;">
      <a href="https://github.com/zippydata/zippy">GitHub</a> · 
      <a href="https://github.com/zippydata/zippy/blob/master/PAPER.md">Paper</a> · 
      <a href="https://github.com/zippydata/zippy/blob/master/CHANGELOG.md">Changelog</a>
    </span>
  </p>
</footer>
