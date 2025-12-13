# ZDS Benchmark Methodology

This document describes the benchmarking methodology used to evaluate ZDS performance against comparable storage solutions.

## Overview

ZDS benchmarks compare **disk-backed, persistent storage solutions** that support JSON document storage. We specifically exclude in-memory-only solutions to ensure fair comparison of I/O performance.

## Compared Solutions

### Python Benchmarks

| Solution | Format | Description |
|----------|--------|-------------|
| **ZDS Native** | JSONL + Binary Index | Rust core with mmap, simd-json, FxHashMap |
| **SQLite** | SQLite DB | Standard embedded database via `sqlite3` |
| **Pandas CSV** | CSV | DataFrame-based, widely used in data science |
| **HuggingFace Datasets** | Arrow | Memory-mapped Arrow format, ML-focused |

### Node.js Benchmarks

| Solution | Format | Description |
|----------|--------|-------------|
| **ZDS Native** | JSONL + Binary Index | Rust NAPI bindings |
| **SQLite** | SQLite DB | Via `better-sqlite3` (synchronous) |
| **LevelDB** | LSM Tree | Via `level` (LevelDB-based) |

## Benchmark Modes

### Cold vs Warm

Every benchmark measures both **cold** and **warm** performance:

- **Cold**: Fresh file/connection open, includes all initialization overhead
  - File open and memory mapping
  - Index loading (for indexed stores)
  - Connection establishment (for databases)
  
- **Warm**: Data structure already loaded, measures operation only
  - Store/connection already open
  - Index already in memory
  - Mmap already established

This distinction is critical because:
1. Cold performance matters for short-lived processes, serverless functions
2. Warm performance matters for long-running services, batch processing

## Workloads

### 1. Write (Bulk Insert)

Measures time to write N records from memory to disk.

**What's measured:**
- Record serialization (JSON encoding)
- File I/O / database insertion
- Index updates
- Flush/sync to disk

**Methodology:**
```python
# Cold only (write is inherently "cold")
start = time.perf_counter()
for record in data:
    store.put(record["id"], record)
store.flush()
elapsed = time.perf_counter() - start
```

### 2. Read All (Full Scan)

Measures time to read all N records into memory.

**What's measured (cold):**
- File/connection open
- Index loading
- Sequential read of all records
- JSON deserialization

**What's measured (warm):**
- Sequential read only (file already open)
- JSON deserialization

**Methodology:**
```python
# Cold
start = time.perf_counter()
store = Store.open(path)         # Includes index load
docs = store.scan()              # Read all
elapsed = time.perf_counter() - start

# Warm
store = Store.open(path)         # Pre-warm (not measured)
start = time.perf_counter()
docs = store.scan()              # Read all only
elapsed = time.perf_counter() - start
```

### 3. Random Access (Point Lookups)

Measures time to retrieve R random records by ID.

**What's measured (cold):**
- File/connection open
- Index loading
- R individual lookups by primary key

**What's measured (warm):**
- R individual lookups only

**Methodology:**
```python
# Cold
sample_ids = random.sample(all_ids, R)
start = time.perf_counter()
store = Store.open(path)
docs = [store.get(id) for id in sample_ids]
elapsed = time.perf_counter() - start

# Warm
store = Store.open(path)         # Pre-warm (not measured)
start = time.perf_counter()
docs = [store.get(id) for id in sample_ids]
elapsed = time.perf_counter() - start
```

## Test Data

Benchmarks use deterministic synthetic data:

```python
{
    "id": "record_00000001",
    "name": "User 1",
    "email": "user1@example.com",
    "age": 42,
    "score": 87.5,
    "active": true,
    "tags": ["a", "b"],
    "metadata": {
        "created": "2025-01-15",
        "source": "web"
    }
}
```

**Properties:**
- Fixed seed (42) for reproducibility
- ~200 bytes per record (JSON)
- Mix of data types: strings, numbers, booleans, arrays, nested objects
- Variable-length arrays (1-3 tags)

**Default sizes:**
- Records: 100,000
- Random lookups: 1,000

## Metrics

### Throughput

Primary metric: **records per second (rec/s)**

```
throughput = record_count / time_seconds
```

Displayed with K/M suffixes:
- `1.2M rec/s` = 1,200,000 records/second
- `450k rec/s` = 450,000 records/second

### Timing Breakdown

Each benchmark reports sub-timings:

| Phase | Description |
|-------|-------------|
| `open` | Store/file/connection open |
| `scan` | Sequential read of records |
| `lookup` | Individual record retrieval |
| `write` | Record insertion |
| `flush` | Sync to disk |

Example output:
```
read_all:    870k rec/s  (115ms) [open:45, scan:70] (cold)
read_all:   1.02M rec/s   (98ms) [scan:98] (warm)
```

### Storage Size

Reported in MB for write operations to compare storage efficiency.

## Fairness Considerations

### What We Measure

1. **End-to-end latency**: Time from API call to data available
2. **Real-world patterns**: Cold start, warm cache, mixed workloads
3. **Apples-to-apples**: Same data, same operations, same machine

### What We Don't Measure

1. **In-memory only**: Excluded (unfair comparison)
2. **Network storage**: Local disk only
3. **Concurrent access**: Single-threaded benchmarks

### Platform-Specific Notes

**ZDS Native:**
- Uses mmap for reads (OS page cache applies)
- Binary index loaded into memory on open
- simd-json for fast JSON parsing
- FxHashMap for O(1) key lookups

**SQLite:**
- WAL mode enabled for write performance
- `synchronous=NORMAL` (not FULL)
- JSON stored as TEXT column
- Primary key index on id

**Pandas:**
- Warm "read" is DataFrame.copy() (already parsed)
- Not a fair warm comparison (different semantics)
- Included for reference only

**HuggingFace Datasets:**
- Memory-mapped Arrow format
- Optimized for sequential ML training access
- Warm iterate is extremely fast (zero-copy)

## Running Benchmarks

### Python

```bash
cd benchmarks/python
pip install pandas datasets orjson

# Default: 100k records
python benchmark_io.py

# Custom size
python benchmark_io.py -n 500000 -r 5000

# Save results
python benchmark_io.py -o results.json
```

### Node.js

```bash
cd benchmarks/nodejs
npm install

# Default: 100k records
node benchmark_io.js

# Custom size
node benchmark_io.js -n=500000
```

## Interpreting Results

### When ZDS Wins

- **Write**: Bulk JSONL write + binary index is very fast
- **Random warm**: O(1) hash lookup + mmap seek is optimal
- **Read all warm**: mmap + simd-json is highly optimized

### When Others Win

- **Pandas cold read**: CSV parser is C-optimized, no index overhead
- **HF Datasets warm**: Zero-copy Arrow is fastest for iteration
- **SQLite complex queries**: SQL query optimizer, joins, aggregations

### Choosing the Right Tool

| Use Case | Recommendation |
|----------|----------------|
| ML training data | ZDS or HF Datasets |
| Document store | ZDS |
| Complex queries | SQLite |
| Data analysis | Pandas |
| Serverless (cold start matters) | SQLite or Pandas |
| Long-running service | ZDS |

---

## Rust Core Benchmarks

The Rust core library (`zippy_core`) provides the underlying engine for all language bindings. Benchmarking the core directly eliminates FFI overhead and shows the raw engine performance.

### Comparative Benchmarks

We compare ZDS against SQLite (via rusqlite) and Sled for JSON document workloads.

#### Running Benchmarks

```bash
cd crates/zippy_core

# Run all comparison benchmarks
cargo bench --bench comparison

# Run specific suites
cargo bench --bench ingestion
cargo bench --bench random_access
cargo bench --bench scan
```

### Write Performance (Apple M3 Max)

| Records | ZDS | SQLite (WAL) | Sled |
|---------|-----|--------------|------|
| 1,000 | **8.5 ms** (117k/s) | 20 ms (50k/s) | 60 ms (17k/s) |
| 10,000 | **59 ms** (170k/s) | 163 ms (61k/s) | 114 ms (88k/s) |

**Observations:**
- ZDS is **2-3x faster** than SQLite for writes
- ZDS is **1.5-7x faster** than Sled for writes
- ZDS uses append-only JSONL with buffered I/O

### Read All (Scan) Performance

| Records | ZDS Cold | ZDS Warm | SQLite Cold | SQLite Warm | Sled Cold | Sled Warm |
|---------|----------|----------|-------------|-------------|-----------|-----------|
| 1,000 | 2.8 ms | 1.2 ms | **0.6 ms** | **0.1 ms** | 7.0 ms | 0.2 ms |
| 10,000 | 24 ms | 9.8 ms | **2.7 ms** | **1.9 ms** | 12 ms | 1.9 ms |
| 100,000 | 263 ms | 95 ms | **21 ms** | **20 ms** | 80 ms | 22 ms |

**Throughput (warm):**
| Records | ZDS | SQLite | Sled |
|---------|-----|--------|------|
| 1,000 | 850 K/s | **9.2 M/s** | 5.3 M/s |
| 10,000 | 1.0 M/s | **5.2 M/s** | 5.2 M/s |
| 100,000 | 1.1 M/s | **5.0 M/s** | 4.6 M/s |

**Observations:**
- SQLite is **5-10x faster** for full scans (optimized for reads)
- ZDS scan includes JSON parsing overhead
- Cold start penalty: ZDS ~2.5x, SQLite ~1.05x, Sled ~3.6x

### Random Access Performance (1000 lookups on 10k docs)

| Store | Time | Throughput |
|-------|------|------------|
| ZDS | 2.0 ms | 505 K/s |
| SQLite | 2.2 ms | 453 K/s |
| Sled | **0.27 ms** | **3.6 M/s** |

**Observations:**
- ZDS and SQLite have comparable random access performance
- Sled is ~7x faster due to LSM-tree architecture optimized for lookups
- ZDS uses mmap + binary index for O(1) access

### When to Use Each

| Use Case | Best Choice | Why |
|----------|-------------|-----|
| **Write-heavy ML pipelines** | **ZDS** | Fastest writes, human-readable format |
| **Read-heavy analytics** | SQLite | Optimized query engine |
| **Key-value lookups** | Sled | LSM-tree optimized for point reads |
| **Cross-platform datasets** | **ZDS** | No binary dependencies, works everywhere |
| **Schema flexibility** | **ZDS** | Schema-on-read, no migrations |
| **Complex queries** | SQLite | Full SQL support |

### Trade-offs Summary

| Aspect | ZDS | SQLite | Sled |
|--------|-----|--------|------|
| Write speed | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| Read speed | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| Random access | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Human readable | ⭐⭐⭐ | ❌ | ❌ |
| No dependencies | ⭐⭐⭐ | ❌ (C lib) | ⭐⭐⭐ |
| Schema flexibility | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Query support | ⭐ (via DuckDB) | ⭐⭐⭐ | ❌ |

---

## CLI Benchmarks

The CLI (`zippy` binary) can be benchmarked for shell scripting use cases.

```bash
# Build release binary
cargo build --release

# Benchmark commands with hyperfine
hyperfine './target/release/zippy scan ./data -c train --jsonl > /dev/null'
hyperfine './target/release/zippy stats ./data'
```

---

## Version Information

Benchmarks run with:
- Python 3.12+
- Node.js 20+
- Rust 1.75+
- Apple M3 Max
- macOS 15

Results may vary based on:
- Disk speed (SSD vs HDD)
- Available RAM
- OS page cache state
- Background processes (current benchmarks were executed under existing system load)
