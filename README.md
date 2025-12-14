# Zippy Data System (ZDS)

<img src="./z.png" width="64" alt="Zippy Data System logo">

A high-performance, human-readable document store for modern data workflows.

[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-18%2B-green)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> 📄 **[Read the Technical Paper](./PAPER.md)** - Comprehensive documentation, format specification, and design rationale

## Why ZDS?

```
┌─────────────────────────────────────────────────────────────┐
│  "I just want to save my data and read it back later,       │
│   without fighting with schemas, binary formats,            │
│   or lock-in. And I want it to be fast."                    │
└─────────────────────────────────────────────────────────────┘
```

- **Human-readable**: JSONL storage you can inspect with `cat` and edit with `vim`
- **Schema-flexible**: Each document defines its own shape
- **Zero lock-in**: Standard ZIP container, extract with any tool
- **Cross-platform**: Python, Node.js, Rust, and DuckDB
- **Competitive performance**: 20x faster writes than SQLite

## Features

- **High-performance**: 4M+ writes/sec, 500k+ reads/sec (Native Rust store)
- **Document-oriented**: Stable IDs, random access, schema-per-document
- **Crash-safe**: Append-only journaling with atomic commits
- **Integrations**: HuggingFace Datasets, Pandas, DuckDB SQL
- **Multi-language**: Python, Node.js, Rust core
- **Developer-friendly**: VSCode extension, CLI tools

## Installation

### Python Package

```bash
# From source
cd python
pip install -e .

# With optional dependencies
pip install -e ".[pandas,arrow]"
pip install duckdb  # For SQL queries
```

### Rust CLI

```bash
cargo build --release
./target/release/zippy --help
```

### VSCode Extension

```bash
cd vscode-extension
npm install
npm run compile
# Press F5 to launch in development mode
```

## Quick Start

### Python: Load Remote Datasets

```python
from zippy import load_remote

# Load from GitHub (default), GitLab, or any Git host
dataset = load_remote("zippydata/sentiment-analysis")
dataset = load_remote("zippydata/sentiment-analysis", collection="train")
dataset = load_remote("gitlab.com/user/repo")  # GitLab

# Load specific version
dataset = load_remote("zippydata/sentiment-analysis", revision="v2.0")

# Load from local path
dataset = load_remote("./my_local_dataset")

# Iterate
for doc in dataset:
    print(doc)
```

### Python: HuggingFace Integration

```python
from zippy import from_hf, to_hf, to_hf_dict

# Convert HuggingFace Dataset to ZDS
from datasets import load_dataset
hf = load_dataset("imdb")
zds = from_hf(hf, "./imdb_zds")  # Creates train/test collections

# Convert ZDS back to HuggingFace
hf_train = to_hf("./imdb_zds", collection="train")
hf_dict = to_hf_dict("./imdb_zds")  # All collections as DatasetDict

# Use with transformers
from transformers import Trainer
trainer = Trainer(train_dataset=hf_train, ...)
```

### Python: Basic Usage

```python
from zippy import ZDSStore, ZDataset

# Create a store
store = ZDSStore.open("./my_data", collection="users")

# Add documents
store.put("user_001", {"name": "Alice", "age": 28, "tags": ["dev"]})
store.put("user_002", {"name": "Bob", "age": 35, "tags": ["manager"]})

# Retrieve
user = store.get("user_001")
print(user["name"])  # Alice

# Scan with filter
for doc in store.scan(predicate={"age": 28}):
    print(doc)

# Use as dataset
dataset = ZDataset(store)
print(len(dataset))  # 2
print(dataset[0])    # First document

# Transformations
filtered = dataset.filter(lambda x: x["age"] > 30)
shuffled = dataset.shuffle(seed=42)
```

### Python: ML Training

```python
from zippy import ZDSStore, ZIterableDataset

# Load training data
store = ZDSStore.open("./ml_data", collection="train")
dataset = ZIterableDataset(store)

# Streaming with shuffle buffer
for epoch in range(3):
    shuffled = dataset.shuffle(buffer_size=1000, seed=epoch)
    for batch in shuffled.batch(32):
        features = [item["features"] for item in batch]
        labels = [item["label"] for item in batch]
        # train_step(features, labels)
```

### Python: SQL Queries with DuckDB

```python
from zippy.duckdb_compat import sql, ZDSConnection

# Quick query
results = sql("./my_data", "users", "SELECT * FROM data WHERE age > 30")

# Multiple collections
with ZDSConnection("./my_data") as zds:
    zds.register("users")
    zds.register("orders")
    
    results = zds.query("""
        SELECT u.name, COUNT(o._id) as order_count
        FROM users u
        LEFT JOIN orders o ON u._id = o.user_id
        GROUP BY u.name
    """)
```

### Python: Pandas Integration

```python
import pandas as pd
from zippy.pandas_compat import read_zds, to_zds

# Save DataFrame to ZDS
df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [95, 87]})
to_zds(df, "./data", collection="scores", doc_id_column="name")

# Load ZDS as DataFrame
df_loaded = read_zds("./data", collection="scores")
```

### CLI Usage

```bash
# Initialize store
zippy init ./my_store

# Add document
zippy put ./my_store -c users -i user_001 -d '{"name": "Alice"}'

# Get document
zippy get ./my_store -c users -i user_001

# Scan collection
zippy scan ./my_store -c users -f name,age -l 10

# Statistics
zippy stats ./my_store -c users

# Pack to archive
zippy pack ./my_store ./my_store.zds
```

## Data Format

ZDS stores data as individual JSON files with metadata:

```
my_store/
├── collections/
│   └── users/
│       ├── docs/
│       │   ├── user_001.json
│       │   └── user_002.json
│       └── meta/
│           ├── manifest.json    # Collection metadata
│           ├── schemas.jsonl    # Schema registry
│           ├── doc_index.jsonl  # Document index
│           ├── order.ids        # Stable iteration order
│           └── journal.log      # Write-ahead log
```

### Schema Modes

**Flexible (default):** Each document can have different fields.

**Strict:** All documents must match the schema of the first document.

```python
# Strict mode
store = ZDSStore.open("./data", collection="products", strict=True)
store.put("p1", {"name": "Widget", "price": 9.99})  # Sets schema
store.put("p2", {"name": "Gadget", "price": 19.99}) # OK
store.put("p3", {"title": "Thing"})  # Error: schema mismatch
```

## Examples

Run the example scripts to see ZDS in action:

```bash
# Install dependencies
pip install pandas duckdb

# Run examples (generates data in examples/data/)
cd python
python ../examples/python/01_basic_usage.py
python ../examples/python/02_ml_dataset.py
python ../examples/python/03_pandas_integration.py
python ../examples/python/04_duckdb_integration.py

# Inspect generated data
ls ../examples/data/01_basic/collections/
cat ../examples/data/01_basic/collections/users/docs/user_001.json
```

See [examples/README.md](examples/README.md) for details.

## Performance

ZDS offers two storage backends optimized for different use cases:

### FastZDSStore (Recommended for bulk operations)

Uses JSONL storage for maximum throughput. Competitive with pandas and HuggingFace datasets.

```python
from zippy import FastZDSStore

# High-throughput bulk writes
with FastZDSStore.open("./data", collection="train") as store:
    for i in range(100000):
        store.put(f"doc_{i}", {"features": [...], "label": i % 10})
```

**Python Benchmark Results (100k records, Apple M3 Max):**

| Approach | Write | Read All (cold) | Read All (warm) | Random (cold) | Random (warm) |
|----------|-------|-----------------|-----------------|---------------|---------------|
| **ZDS Native** | **4.66M** | 292k | **510k** | 7k | **308k** |
| SQLite | 237k | 267k | 263k | 89k | 88k |
| Pandas CSV | 205k | **957k** | *8.18M* | 8k | 227k |
| HF Datasets | 633k | 40k | 40k | 29k | 30k |

*Throughput in records/second. Pandas warm = in-memory DataFrame (not disk-backed).*

**Key findings:**
- **Write: ZDS is 20x faster** than SQLite, 7x faster than HF Datasets
- **Random warm: ZDS is 3.5x faster** than SQLite (308k vs 88k)
- Cold read includes index loading (~146ms for 100k entries)
- See [BENCHMARK.md](./BENCHMARK.md) for methodology

**Node.js Benchmark Results (100k records, Apple M3 Max):**

| Approach | Write | Read All (cold) | Read All (warm) | Random (cold) | Random (warm) |
|----------|-------|-----------------|-----------------|---------------|---------------|
| **ZDS Native** | **4.26M** | 385k | **828k** | 6k | 201k |
| SQLite | 344k | **735k** | 650k | 147k | **263k** |
| LevelDB | 422k | 291k | 443k | 67k | 69k |

*Throughput in records/second.*

**Key findings:**
- **Write: ZDS is 12x faster** than SQLite, 10x faster than LevelDB
- **Read warm: ZDS is 1.3x faster** than SQLite, 1.9x faster than LevelDB

### ZDSStore (Individual files, human-readable)

Each document is a separate JSON file. Best for debugging, git-friendly workflows, and 
interoperability with other tools.

```python
from zippy import ZDSStore

# Human-readable storage
store = ZDSStore.open("./data", collection="train")
store.put("doc_001", {"text": "hello"})
# Creates: ./data/collections/train/docs/doc_001.json
```

### Performance Tips

```python
# 1. Use FastZDSStore for bulk operations
with FastZDSStore.open("./data", collection="train") as store:
    for record in records:
        store.put(record["id"], record)

# 2. Use bulk_write context for ZDSStore
store = ZDSStore.open("./data", collection="train")
with store.bulk_write():  # Defers index updates
    for record in records:
        store.put(record["id"], record)

# 3. Use scan_fast() for full collection reads
for doc in store.scan_fast():
    process(doc)

# 4. Preload for random access workloads
store.preload()  # Caches all documents in memory
doc = store.get("doc_001")  # Fast from cache

# 5. Install orjson for 2-3x faster JSON
pip install orjson
```

## Benchmarks

```bash
# I/O benchmarks
python benchmarks/python/benchmark_io.py -n 10000

# ML training benchmarks
python benchmarks/python/benchmark_ml.py -n 10000
```

See [benchmarks/README.md](benchmarks/README.md) for results.

## Project Structure

```
zippy/
├── crates/
│   ├── zippy_data/      # Rust core engine
│   └── zippy_duckdb/    # DuckDB extension (stub)
├── cli/                 # CLI tool
├── docs/                # Documentation site (Just-the-Docs)
│   ├── docs/            # Guide + API markdown
│   └── assets/          # Site media (logo, styles)
├── python/              # Python package
│   └── zippy/
│       ├── store.py           # ZDSStore
│       ├── dataset.py         # ZDataset (map-style)
│       ├── iterable_dataset.py # ZIterableDataset (streaming)
│       ├── pandas_compat.py   # DataFrame integration
│       └── duckdb_compat.py   # SQL queries
├── vscode-extension/    # VS Code extension
├── examples/            # Example scripts
├── benchmarks/          # Performance benchmarks
├── BENCHMARK.md         # Aggregated benchmark results and methodology
└── README.md            # This file (quickstart + references)

📚 **Docs & Guides**
- Docs site: [`docs/`](docs/) → published at https://zippydata.org
- Package guides for agents: see [AGENTS.md](AGENTS.md) + runtime-specific files in `python/`, `nodejs/`, `crates/zippy_data/`, and `cli/`
```

## API Reference

### ZDSStore

```python
store = ZDSStore.open(path, collection="default", strict=False)

store.put(doc_id, doc)      # Insert/update document
store.get(doc_id)           # Retrieve document (raises KeyError if not found)
store.delete(doc_id)        # Delete document
store.exists(doc_id)        # Check existence
store.count()               # Document count
store.list_doc_ids()        # List all document IDs
store.scan(fields=None, predicate=None)  # Iterate documents

# Dict-style access
store["id"] = doc           # Put
doc = store["id"]           # Get
del store["id"]             # Delete
"id" in store               # Exists
len(store)                  # Count
```

### ZDataset (Map-style)

```python
dataset = ZDataset(store)

len(dataset)                # Length
dataset[0]                  # Index access
dataset[-1]                 # Negative indexing
dataset[0:10]               # Slicing

dataset.select([0, 5, 10])  # Select by indices
dataset.shuffle(seed=42)    # Shuffle
dataset.map(fn)             # Transform each item
dataset.filter(fn)          # Filter items
dataset.take(n)             # First n items
dataset.skip(n)             # Skip first n
dataset.batch(size)         # Iterate in batches
dataset.features            # Inferred schema
```

### ZIterableDataset (Streaming)

```python
dataset = ZIterableDataset(store)

for item in dataset:        # Iterate
    pass

dataset.shuffle(buffer_size=1000, seed=42)  # Shuffle buffer
dataset.map(fn)             # Lazy transform
dataset.filter(fn)          # Lazy filter
dataset.take(n)             # Take first n
dataset.skip(n)             # Skip first n
dataset.batch(size)         # Yield batches
```

### DuckDB Integration

```python
from zippy.duckdb_compat import sql, aggregate, count_where, ZDSConnection

# Quick queries
results = sql(path, collection, "SELECT * FROM data WHERE x > 10")
results = aggregate(path, collection, "category", "SUM(amount)")
count = count_where(path, collection, "status = 'active'")

# Connection wrapper
with ZDSConnection(path) as zds:
    zds.register("collection_a")
    zds.register("collection_b", view_name="alias")
    results = zds.query("SELECT * FROM collection_a JOIN alias ON ...")
    zds.export("SELECT ...", collection="output", id_column="id")
```

## Recipes

### Recipe: Convert CSV to ZDS

```python
import pandas as pd
from zippy.pandas_compat import to_zds

df = pd.read_csv("data.csv")
to_zds(df, "./my_store", collection="imported", doc_id_column="id")
```

### Recipe: Export ZDS to CSV

```python
from zippy.pandas_compat import read_zds

df = read_zds("./my_store", collection="data")
df.to_csv("exported.csv", index=False)
```

### Recipe: Merge Collections

```python
from zippy import ZDSStore

store_a = ZDSStore.open("./data", collection="train_a")
store_b = ZDSStore.open("./data", collection="train_b")
merged = ZDSStore.open("./data", collection="train_merged")

for doc_id in store_a.list_doc_ids():
    merged.put(f"a_{doc_id}", store_a.get(doc_id))
for doc_id in store_b.list_doc_ids():
    merged.put(f"b_{doc_id}", store_b.get(doc_id))
```

### Recipe: Backup Collection

```bash
# Pack to archive
zippy pack ./my_store ./backup.zds

# Restore from archive
zippy unpack ./backup.zds ./restored
```

### Recipe: Query with SQL and Export

```python
from zippy.duckdb_compat import ZDSConnection

with ZDSConnection("./my_store") as zds:
    zds.register("raw_data")
    
    # Query and export aggregated results
    zds.export(
        """
        SELECT category, COUNT(*) as count, AVG(value) as avg_value
        FROM raw_data
        GROUP BY category
        HAVING count > 10
        """,
        collection="aggregated",
        id_column="category"
    )
```

### Recipe: Training Loop with Checkpoints

```python
from zippy import ZDSStore, ZIterableDataset

store = ZDSStore.open("./data", collection="train")

for epoch in range(100):
    dataset = ZIterableDataset(store).shuffle(buffer_size=10000, seed=epoch)
    
    for batch in dataset.batch(32):
        # Training step
        pass
    
    # Save checkpoint
    checkpoint_store = ZDSStore.open("./checkpoints", collection=f"epoch_{epoch}")
    checkpoint_store.put("model", {"weights": "...", "epoch": epoch})
```

## Tests

```bash
# Rust tests
cargo test

# Python tests
cd python
pip install pytest
pytest tests/ -v
```

## Contributing

Contributions welcome! Please open issues or submit pull requests on GitHub.

## License

MIT License - see [LICENSE](LICENSE) for details.

Copyright © 2025 [Omar Kamali](https://omarkamali.com)

<img src="./z.png" width="64" alt="Zippy Data System logo">