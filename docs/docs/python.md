---
layout: default
title: Python Guide
parent: Documentation
nav_order: 2
---

# Python Guide

Complete guide to using ZDS with Python.

## Installation

```bash
pip install zippy-data
```

For optional integrations:
```bash
pip install zippy-data[pandas]    # DataFrame support
pip install zippy-data[duckdb]    # SQL queries
pip install zippy-data[hf]        # HuggingFace conversion
pip install zippy-data[all]       # Everything
```

## Quick Reference

```python
from zippy import (
    # Stores
    ZDSStore,           # Standard store
    FastZDSStore,       # High-performance JSONL store
    
    # Datasets
    ZDataset,           # Map-style (random access)
    ZIterableDataset,   # Streaming (memory efficient)
    
    # Remote loading
    load_remote,        # Load from GitHub, local path, etc.
    
    # HuggingFace
    from_hf, to_hf,     # Convert to/from HF Dataset
    
    # Pandas
    read_zds, to_zds,   # DataFrame conversion
    
    # DuckDB
    query_zds,          # SQL queries
    register_zds,       # Register in DuckDB connection
)
```

---

## ZDSStore

The primary interface for document operations.

### Opening a Store

```python
from zippy import ZDSStore

# Create or open a store
store = ZDSStore.open(
    path="./my_data",           # Directory path
    collection="train",         # Collection name
    strict=False,               # Schema enforcement (default: flexible)
)

# Context manager (auto-close)
with ZDSStore.open("./data", "train") as store:
    store.put("doc1", {"text": "hello"})
```

### CRUD Operations

```python
# Put (create or update)
store.put("doc_001", {"text": "Hello", "label": 1})
store.put("doc_002", {"text": "World", "tags": ["a", "b"]})

# Get by ID
doc = store.get("doc_001")
print(doc)  # {"text": "Hello", "label": 1}

# Dict-style access
store["doc_003"] = {"text": "New doc"}
print(store["doc_003"])

# Check existence
if "doc_001" in store:
    print("Found!")

# Delete
store.delete("doc_002")

# Count
print(len(store))  # Number of documents
```

### Scanning

```python
# Scan all documents
for doc in store.scan():
    print(doc)

# With projection (only specific fields)
for doc in store.scan(fields=["text", "label"]):
    print(doc)  # Only contains text and label

# With predicate (filter)
for doc in store.scan(predicate={"label": 1}):
    print(doc)  # Only label=1 documents

# List all document IDs
ids = store.list_doc_ids()
```

### Strict Mode

Enforce consistent schemas:

```python
# Enable strict mode
store = ZDSStore.open("./data", "products", strict=True)

# First document defines the schema
store.put("prod_001", {"name": "Widget", "price": 9.99})

# Same schema works
store.put("prod_002", {"name": "Gadget", "price": 19.99})

# Different schema fails!
try:
    store.put("prod_003", {"title": "Thing", "cost": 5.99})
except ValueError as e:
    print(f"Schema mismatch: {e}")
```

---

## ZDataset

HuggingFace-compatible map-style dataset with random access.

### Creating a Dataset

```python
from zippy import ZDataset, ZDSStore

# From store
store = ZDSStore.open("./data", "train")
dataset = ZDataset(store)

# Or directly
dataset = ZDataset.from_store("./data", collection="train")
```

### Indexing and Slicing

```python
# Length
print(len(dataset))  # 1000

# Index access
first = dataset[0]
last = dataset[-1]

# Slicing
subset = dataset[10:20]   # Returns new ZDataset
every_10th = dataset[::10]
```

### Transformations

```python
# Shuffle (returns new dataset)
shuffled = dataset.shuffle(seed=42)

# Filter
positive = dataset.filter(lambda x: x["label"] == 1)

# Map
def add_length(doc):
    return {**doc, "length": len(doc["text"])}

with_length = dataset.map(add_length)

# Select specific indices
selected = dataset.select([0, 5, 10, 15])

# Take first N
first_100 = dataset.take(100)

# Chain operations
result = (
    dataset
    .filter(lambda x: x["score"] > 0.5)
    .map(lambda x: {**x, "processed": True})
    .shuffle(seed=123)
    .take(50)
)
```

### Batching

```python
# Iterate in batches
for batch in dataset.batch(32):
    # batch is a list of documents
    print(f"Batch size: {len(batch)}")
    
# Or collect all batches
batches = list(dataset.batch(32))
```

### Features

```python
# Infer features from first document
print(dataset.features)
# {'text': 'string', 'label': 'int', 'tags': 'list'}
```

---

## ZIterableDataset

Memory-efficient streaming for large datasets.

```python
from zippy import ZIterableDataset

# Create iterable dataset
iterable = ZIterableDataset.from_store("./large_data", "train")

# Streaming iteration (no random access)
for doc in iterable:
    process(doc)

# Shuffle with buffer (memory-efficient)
shuffled = iterable.shuffle(buffer_size=1000, seed=42)

# Lazy transformations
processed = (
    iterable
    .filter(lambda x: x["valid"])
    .map(lambda x: transform(x))
    .take(10000)
)

# Batched streaming
for batch in iterable.batch(32):
    train_step(batch)
```

---

## Remote Loading

Load datasets from various sources.

```python
from zippy import load_remote

# Local path
dataset = load_remote("./my_dataset", collection="train")

# GitHub repository
dataset = load_remote("zippydata/example-datasets")

# With specific collection and version
dataset = load_remote(
    "zippydata/example-datasets",
    collection="train",
    revision="v1.0"
)

# Streaming mode for large datasets
for doc in load_remote("zippydata/large", streaming=True):
    process(doc)

# Private repository
dataset = load_remote(
    "myorg/private-repo",
    token=os.environ["GITHUB_TOKEN"]
)
```

---

## HuggingFace Integration

### Convert HuggingFace to ZDS

```python
from datasets import load_dataset
from zippy import from_hf

# Load HuggingFace dataset
hf = load_dataset("imdb", split="train")

# Convert to ZDS
zds = from_hf(hf, "./imdb_zds", collection="train")

# DatasetDict (multiple splits)
hf_dict = load_dataset("imdb")  # Has train and test
zds = from_hf(hf_dict, "./imdb_zds")  # Creates train/ and test/ collections

# With custom ID column
zds = from_hf(hf, "./output", id_column="article_id")
```

### Convert ZDS to HuggingFace

```python
from zippy import to_hf, to_hf_dict

# Single collection
hf = to_hf("./my_data", collection="train")

# Or from ZDataset
hf = to_hf(dataset)

# Multiple collections as DatasetDict
hf_dict = to_hf_dict("./my_data", collections=["train", "test"])
```

---

## Pandas Integration

```python
from zippy import read_zds, to_zds
import pandas as pd

# ZDS to DataFrame
df = read_zds("./data", collection="train")

# DataFrame to ZDS
df = pd.DataFrame({"text": ["a", "b"], "label": [1, 0]})
to_zds(df, "./output", collection="data", id_column="text")
```

---

## DuckDB Integration

```python
from zippy import query_zds, register_zds
import duckdb

# Quick query
results = query_zds(
    "./data",
    "SELECT label, COUNT(*) FROM train GROUP BY label"
)

# Complex queries with connection
conn = duckdb.connect()
register_zds(conn, "./data", collection="train")
register_zds(conn, "./data", collection="metadata")

results = conn.execute("""
    SELECT t.*, m.category
    FROM train t
    JOIN metadata m ON t.id = m.id
    WHERE t.score > 0.8
""").fetchdf()
```

---

## Examples

See the [examples directory](https://github.com/zippydata/zippy/tree/main/examples/python) for complete working examples:

- `01_basic_usage.py` - Core operations
- `02_ml_dataset.py` - ML workflows
- `03_pandas_integration.py` - DataFrame conversion
- `04_duckdb_integration.py` - SQL queries
- `05_huggingface_integration.py` - HF conversion
- `06_remote_datasets.py` - Remote loading
