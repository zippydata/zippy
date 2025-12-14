---
layout: default
title: Getting Started
nav_order: 2
---

# Getting Started
{: .no_toc }

Get up and running with ZDS in under 5 minutes. This guide walks you through installation, creating your first dataset, and understanding what makes ZDS different.

<details open markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
1. TOC
{:toc}
</details>

---

## What is ZDS?

ZDS (Zippy Data System) is a document store designed for ML and data engineering workflows. It stores JSON documents in a human-readable format while providing database-like performance.

**Key benefits:**
- **Human-readable**: Your data is stored as JSONL files you can inspect with `cat`, edit with `vim`, and version with `git`
- **Schema-flexible**: Each document can have different fields—no migrations needed
- **Fast**: O(1) random access, 4.6M writes/second, binary indexes
- **Zero lock-in**: Standard ZIP + JSONL format works without any special tools

---

## Installation

Choose your preferred language:

<div class="code-tabs">

### Python

```bash
pip install zippy-data
```

For all integrations (Pandas, DuckDB, HuggingFace):

```bash
pip install zippy-data[all]
```

### Node.js

```bash
npm install @zippydata/core
```

### Rust

```toml
# Cargo.toml
[dependencies]
zippy_data = "0.1"
```

### CLI

```bash
# macOS
brew install zippydata/tap/zippy

# Or download from releases
curl -L https://github.com/zippydata/zippy/releases/latest/download/zippy-$(uname -m)-apple-darwin.tar.gz | tar xz
sudo mv zippy /usr/local/bin/
```

</div>

---

## Your First Dataset

### Python

```python
from zippy import ZDSStore, ZDataset

# Create a new store
store = ZDSStore.open("./my_first_dataset", collection="examples")

# Add some documents
store.put("greeting_001", {
    "text": "Hello, world!",
    "language": "en",
    "sentiment": "positive"
})

store.put("greeting_002", {
    "text": "Bonjour le monde!",
    "language": "fr", 
    "sentiment": "positive"
})

store.put("greeting_003", {
    "text": "Hola mundo!",
    "language": "es",
    "sentiment": "positive",
    "extra_field": ["this", "is", "flexible"]  # Different schema!
})

print(f"Created {len(store)} documents")

# Retrieve by ID
doc = store.get("greeting_001")
print(doc["text"])  # "Hello, world!"

# Iterate all documents
for doc in store.scan():
    print(f"{doc['language']}: {doc['text']}")
```

### Node.js

```javascript
const { ZdsStore } = require('@zippydata/core');

// Create a new store
const store = ZdsStore.open('./my_first_dataset', 'examples');

// Add documents
store.put('greeting_001', {
    text: 'Hello, world!',
    language: 'en',
    sentiment: 'positive'
});

store.put('greeting_002', {
    text: 'Bonjour le monde!',
    language: 'fr',
    sentiment: 'positive'
});

console.log(`Created ${store.count} documents`);

// Retrieve by ID
const doc = store.get('greeting_001');
console.log(doc.text);  // "Hello, world!"

// Iterate
for (const doc of store.scan()) {
    console.log(`${doc.language}: ${doc.text}`);
}

store.close();
```

### CLI

```bash
# Initialize a store
zippy init ./my_first_dataset -c examples

# Add documents
zippy put ./my_first_dataset -c examples greeting_001 \
    --data '{"text": "Hello, world!", "language": "en"}'

zippy put ./my_first_dataset -c examples greeting_002 \
    --data '{"text": "Bonjour!", "language": "fr"}'

# View a document
zippy get ./my_first_dataset -c examples greeting_001 --pretty

# List all documents
zippy scan ./my_first_dataset -c examples

# Show statistics
zippy stats ./my_first_dataset
```

---

## What Just Happened?

Your data is now stored in a human-readable format:

```bash
$ tree my_first_dataset/
my_first_dataset/
└── collections/
    └── examples/
        ├── meta/
        │   ├── data.jsonl      # Your documents
        │   ├── index.bin       # Binary index for O(1) lookups
        │   └── manifest.json   # Collection metadata
        └── docs/               # (optional file-per-doc mode)

$ cat my_first_dataset/collections/examples/meta/data.jsonl
{"_id":"greeting_001","text":"Hello, world!","language":"en","sentiment":"positive"}
{"_id":"greeting_002","text":"Bonjour le monde!","language":"fr","sentiment":"positive"}
{"_id":"greeting_003","text":"Hola mundo!","language":"es","sentiment":"positive","extra_field":["this","is","flexible"]}
```

No special tools needed to inspect your data!

---

## Working with ML Datasets

### The ZDataset API

For ML workflows, use `ZDataset` which provides a HuggingFace-compatible interface:

```python
from zippy import ZDataset, ZIterableDataset

# Map-style dataset (random access)
dataset = ZDataset.from_store("./my_first_dataset", collection="examples")

# Length and indexing
print(len(dataset))    # 3
print(dataset[0])      # First document
print(dataset[-1])     # Last document

# Shuffle with seed
shuffled = dataset.shuffle(seed=42)

# Filter
english = dataset.filter(lambda x: x["language"] == "en")

# Map transformation
def add_uppercase(doc):
    return {**doc, "text_upper": doc["text"].upper()}

mapped = dataset.map(add_uppercase)

# Batching
for batch in dataset.batch(2):
    print(f"Batch of {len(batch)} documents")

# Streaming (memory-efficient for large datasets)
iterable = ZIterableDataset.from_store("./my_first_dataset", collection="examples")
for doc in iterable.shuffle(buffer_size=100):
    process(doc)
```

### Converting from HuggingFace

Already have HuggingFace datasets? Convert them:

```python
from datasets import load_dataset
from zippy import from_hf, to_hf

# Load any HuggingFace dataset
hf_dataset = load_dataset("imdb", split="train")

# Convert to ZDS
zds = from_hf(hf_dataset, "./imdb_zds", collection="train")
print(f"Converted {len(zds)} documents")

# Now you can inspect with standard tools
# cat ./imdb_zds/collections/train/meta/data.jsonl | head -1 | jq .

# Convert back when needed
hf_back = to_hf(zds)
```

---

## DuckDB Integration

Query your data with SQL:

```python
from zippy import query_zds, register_zds
import duckdb

# Quick query
results = query_zds(
    "./my_first_dataset",
    "SELECT language, COUNT(*) as count FROM examples GROUP BY language"
)
print(results)
# [{'language': 'en', 'count': 1}, {'language': 'fr', 'count': 1}, ...]

# Register in DuckDB session for complex queries
conn = duckdb.connect()
register_zds(conn, "./my_first_dataset", collection="examples")

conn.execute("""
    SELECT * FROM examples 
    WHERE sentiment = 'positive'
    ORDER BY language
""").fetchall()
```

---

## Packaging for Distribution

Pack your dataset into a single `.zds` file:

```bash
# Pack
zippy pack ./my_first_dataset my_dataset.zds

# Share the .zds file...

# Recipients unpack
zippy unpack my_dataset.zds ./extracted

# Or just unzip (it's a ZIP file!)
unzip my_dataset.zds -d extracted/
```

---

## Next Steps

- **[Python Guide](./python)** - Full API reference
- **[Node.js Guide](./nodejs)** - JavaScript usage
- **[CLI Reference](./cli)** - All commands
- **[Format Specification](./format)** - Technical details
- **[Examples](https://github.com/zippydata/zippy/tree/master/examples)** - More code samples
