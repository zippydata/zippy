# ZDS Examples

This directory contains example scripts demonstrating ZDS functionality across all supported languages.

## Directory Structure

```
examples/
├── python/      # Python examples
├── nodejs/      # Node.js examples
├── rust/        # Rust examples
├── cli/         # CLI shell script examples
├── data/        # Generated data (gitignored)
└── README.md    # This file
```

## Quick Start

### Python

```bash
# Install dependencies
pip install pandas duckdb datasets

# Run examples (from project root)
cd python
python ../examples/python/01_basic_usage.py
python ../examples/python/02_ml_dataset.py
python ../examples/python/03_pandas_integration.py
python ../examples/python/04_duckdb_integration.py
python ../examples/python/05_huggingface_integration.py
python ../examples/python/06_remote_datasets.py
```

### Node.js

```bash
# Build the Node.js bindings first
cd nodejs && npm run build && cd ..

# Run examples
node examples/nodejs/01_basic_usage.js
node examples/nodejs/02_streaming_data.js
```

### Rust

```bash
# Run examples
cd examples/rust
cargo run --bin basic_usage
cargo run --bin streaming_data
cargo run --bin ml_dataset
```

### CLI

```bash
# Build CLI first
cargo build

# Run shell script examples
bash examples/cli/01_basic_commands.sh
bash examples/cli/02_pack_unpack.sh
bash examples/cli/03_data_pipeline.sh
```

---

## Python Examples

### 01_basic_usage.py
Core ZDS operations:
- Creating/opening stores
- Put, get, delete documents
- Scanning with predicates and projections
- Map-style datasets (ZDataset)
- Iterable/streaming datasets (ZIterableDataset)
- Data persistence

**Output:** `examples/data/01_basic/`

### 02_ml_dataset.py
Machine learning workflows:
- Text classification datasets
- Object detection annotations
- Question-answering pairs
- Multi-epoch training simulation

**Output:** `examples/data/02_ml/`

### 03_pandas_integration.py
DataFrame integration:
- DataFrame → ZDS conversion
- ZDS → DataFrame loading
- Large dataset handling
- Query and aggregation

**Requires:** `pip install pandas`
**Output:** `examples/data/03_pandas/`

### 04_duckdb_integration.py
SQL querying with DuckDB:
- Basic SQL queries
- Aggregations and analytics
- Window functions
- Cross-collection joins
- Export query results

**Requires:** `pip install duckdb pandas`
**Output:** `examples/data/04_duckdb/`

### 05_huggingface_integration.py
HuggingFace ecosystem integration:
- Convert HuggingFace Dataset to ZDS
- Convert ZDS to HuggingFace Dataset
- Work with DatasetDict (multiple splits)
- Custom ID columns
- Training workflow simulation

**Requires:** `pip install datasets`
**Output:** `examples/data/05_huggingface/`

### 06_remote_datasets.py
Remote dataset loading:
- Load from local paths
- GitHub/GitLab repository formats
- Dataset info without downloading
- Caching behavior
- Streaming mode for large datasets

**Output:** `examples/data/06_remote/`

---

## Node.js Examples

### 01_basic_usage.js
Core operations with Node.js bindings:
- ZdsStore CRUD operations
- BulkWriter for high-throughput ingestion
- Raw JSONL operations
- Store information

**Output:** `examples/data/nodejs_01_basic/`

### 02_streaming_data.js
Streaming and bulk operations:
- Large dataset creation
- Stream processing
- Batch processing
- Filter and transform pipelines
- Raw JSONL streaming

**Output:** `examples/data/nodejs_02_streaming/`

---

## Rust Examples

### basic_usage.rs
Core Rust API:
- FastStore operations (JSONL-based)
- Engine API (JSON file-based)
- Scanning with predicates/projections
- Collection statistics

**Output:** `examples/data/rust_01_basic/`

### streaming_data.rs
High-performance operations:
- Bulk ingestion (50K+ docs)
- Scan all documents
- Raw JSONL blob operations
- Filtered processing pipelines

**Output:** `examples/data/rust_02_streaming/`

### ml_dataset.rs
Machine learning with Rust:
- Text classification datasets
- Object detection annotations
- Question-answering pairs
- Training loop simulation

**Output:** `examples/data/rust_03_ml/`

---

## CLI Examples

### 01_basic_commands.sh
Basic CLI operations:
- Initialize stores
- Put, get, delete documents
- List collections
- Scan with options
- Statistics and validation

### 02_pack_unpack.sh
Archive operations:
- Pack store into .zds archive
- Unpack archive to folder
- Verify restored data

### 03_data_pipeline.sh
Pipeline integration:
- Read from stdin
- JSONL output
- Integration with jq
- Batch import from files
- Automated backups

---

## Generated Data

Running the examples creates data in `examples/data/`:

```
examples/data/
├── 01_basic/              # Python basic
├── 02_ml/                 # Python ML
├── 03_pandas/             # Python pandas
├── 04_duckdb/             # Python DuckDB
├── 05_huggingface/        # Python HuggingFace
├── 06_remote/             # Python remote
├── nodejs_01_basic/       # Node.js basic
├── nodejs_02_streaming/   # Node.js streaming
├── rust_01_basic/         # Rust basic
├── rust_02_streaming/     # Rust streaming
├── rust_03_ml/            # Rust ML
├── cli_01_basic/          # CLI basic
├── cli_02_pack/           # CLI pack/unpack
└── cli_03_pipeline/       # CLI pipeline
```

## Inspecting Generated Data

Each document is stored as a JSON file:

```bash
# View a document
cat examples/data/01_basic/collections/users/docs/user_001.json

# List all documents in a collection
ls examples/data/01_basic/collections/users/docs/

# View collection metadata
cat examples/data/01_basic/collections/users/meta/manifest.json
```

Use the CLI:

```bash
# Build CLI first
cargo build

# List collections
./target/debug/zippy list examples/data/01_basic

# Get document
./target/debug/zippy get examples/data/01_basic -c users user_001

# Scan collection
./target/debug/zippy scan examples/data/01_basic -c users -l 5
```

Or use Python interactively:

```python
from zippy import ZDSStore, ZDataset

# Open existing data
store = ZDSStore.open("examples/data/01_basic", collection="users")
print(f"Found {len(store)} users")

# Iterate
for doc in store.scan():
    print(doc["name"])

# Random access
dataset = ZDataset(store)
print(dataset[0])
```
