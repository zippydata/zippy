---
layout: default
title: Benchmarks
parent: Documentation
nav_order: 7
---

# Benchmarks

ZDS is designed for high-performance document storage. Here's how it compares to alternatives.

## Summary

| Operation | ZDS | SQLite | Pandas CSV | HF Datasets |
|-----------|-----|--------|------------|-------------|
| **Write** | **4.66M** rec/s | 237k | 205k | 633k |
| **Read All** (warm) | **510k** rec/s | 263k | 8.18M* | 40k |
| **Random Access** (warm) | **308k** rec/s | 88k | 227k | 30k |

*Pandas warm = in-memory DataFrame (different semantics)

**Test conditions:** Apple M3 Max, 100,000 records (~200 bytes each), macOS 15

## Key Findings

### Write Performance

ZDS achieves **20x faster writes** than SQLite:

```
SQLite     ████████░░░░░░░░░░░░░░░░░░░ 237k rec/s
LevelDB    ██████████░░░░░░░░░░░░░░░░░ 422k rec/s
HF Dataset ███████████████░░░░░░░░░░░░ 633k rec/s
ZDS Native ████████████████████████████████████████ 4.66M rec/s ★
```

**Why?** ZDS uses append-only JSONL writes with buffered I/O. No transaction overhead, no WAL, no index updates during writes. The binary index is built lazily.

### Random Access Performance

ZDS achieves **3.5x faster random lookups** than SQLite (warm):

```
HF Dataset ███░░░░░░░░░░░░░░░░░░░░░░░░ 30k rec/s
SQLite     ██████░░░░░░░░░░░░░░░░░░░░░ 88k rec/s  
Pandas     ████████████████░░░░░░░░░░░ 227k rec/s
ZDS Native ███████████████████████████ 308k rec/s ★
```

**Why?** O(1) FxHashMap lookup + mmap seek. No query parsing, no B-tree traversal. Direct offset-based access.

### Read All Performance

For sequential reads, Pandas CSV wins on cold starts due to optimized C parser. ZDS excels in warm scenarios:

| Approach | Cold | Warm |
|----------|------|------|
| Pandas CSV | **957k** | 8.18M* |
| ZDS Native | 292k | **510k** |
| SQLite | 267k | 263k |
| HF Datasets | 40k | 40k |

*In-memory DataFrame (not comparable)

---

## Python Benchmarks

### Full Results (100k records)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Python Benchmark (100k records)                      │
├──────────────┬─────────┬──────────────┬──────────────┬──────────────────┤
│   Approach   │  Write  │ Read (cold)  │ Read (warm)  │ Random (warm)    │
├──────────────┼─────────┼──────────────┼──────────────┼──────────────────┤
│ ZDS Native   │ 4.66M ★ │    292k      │    510k      │   308k ★         │
│ SQLite       │  237k   │    267k      │    263k      │    88k           │
│ Pandas CSV   │  205k   │    957k ★    │   8.18M †    │   227k           │
│ HF Datasets  │  633k   │     40k      │     40k      │    30k           │
└──────────────┴─────────┴──────────────┴──────────────┴──────────────────┘
                                                    † in-memory DataFrame
```

### Running Python Benchmarks

```bash
cd benchmarks/python
pip install pandas datasets orjson

# Default: 100k records
python benchmark_io.py

# Custom size
python benchmark_io.py -n 500000 -r 5000

# Save results to JSON
python benchmark_io.py -o results.json
```

---

## Node.js Benchmarks

### Full Results (100k records)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Node.js Benchmark (100k records)                      │
├──────────────┬─────────┬──────────────┬──────────────┬──────────────────┤
│   Approach   │  Write  │ Read (cold)  │ Read (warm)  │ Random (warm)    │
├──────────────┼─────────┼──────────────┼──────────────┼──────────────────┤
│ ZDS Native   │ 4.26M ★ │    385k      │   828k ★     │   201k           │
│ SQLite       │  344k   │    735k ★    │    650k      │   263k ★         │
│ LevelDB      │  422k   │    291k      │    443k      │    69k           │
└──────────────┴─────────┴──────────────┴──────────────┴──────────────────┘
```

### Running Node.js Benchmarks

```bash
cd benchmarks/nodejs
npm install

# Default: 100k records  
node benchmark_io.js

# Custom size
node benchmark_io.js -n=500000
```

---

## Rust Core Benchmarks

For maximum performance, the Rust core library provides comparative benchmarks against SQLite and Sled.

```bash
cd crates/zippy_core
cargo bench --bench comparison
```

### Write Performance (Apple M3 Max)

| Records | ZDS | SQLite | Sled |
|---------|-----|--------|------|
| 1,000 | **8.5 ms** | 20 ms | 60 ms |
| 10,000 | **59 ms** | 163 ms | 114 ms |

### Read Performance (Warm)

| Records | ZDS | SQLite | Sled |
|---------|-----|--------|------|
| 10,000 | 9.8 ms | **1.9 ms** | 1.9 ms |
| 100,000 | 95 ms | **20 ms** | 22 ms |

### Random Access (1000 lookups on 10k docs)

| Store | Time | Throughput |
|-------|------|------------|
| ZDS | 2.0 ms | 505 K/s |
| SQLite | 2.2 ms | 453 K/s |
| Sled | **0.27 ms** | **3.6 M/s** |

### Sample Results

```
ingestion_buffered/buffered_write/10000
                        time:   [2.8 ms 2.9 ms 3.0 ms]
                        thrpt:  [3.3M 3.4M 3.5M elem/s]

random_access/get_by_id/10000
                        time:   [1.2 µs 1.3 µs 1.4 µs]

scan/full_scan/10000    time:   [8.2 ms 8.4 ms 8.6 ms]
                        thrpt:  [1.16M 1.19M 1.22M elem/s]
```

---

## Methodology

### Cold vs Warm

- **Cold**: Fresh process, includes file open and index loading
- **Warm**: Store already open, measures operation only

### Test Data

Each record is ~200 bytes with mixed types:

```json
{
    "id": "record_00000001",
    "name": "User 1",
    "email": "user1@example.com",
    "age": 42,
    "score": 87.5,
    "active": true,
    "tags": ["a", "b"],
    "metadata": {"created": "2025-01-15", "source": "web"}
}
```

### What We Measure

1. **End-to-end latency**: Time from API call to data available
2. **Real-world patterns**: Cold start, warm cache, mixed workloads
3. **Apples-to-apples**: Same data, same operations, same machine

### Fairness Notes

- **Pandas warm read** is an in-memory DataFrame—not a fair storage comparison
- **SQLite** uses WAL mode and `synchronous=NORMAL`
- **ZDS** benefits from OS page cache for mmap reads
- **HuggingFace Datasets** uses Arrow, optimized for sequential iteration

See [BENCHMARK.md](https://github.com/zippydata/zippy/blob/main/BENCHMARK.md) for complete methodology.

---

## When to Use What

| Scenario | Recommendation |
|----------|----------------|
| Bulk data ingestion | **ZDS** |
| Random key-value lookups | **ZDS** |
| Schema-flexible documents | **ZDS** |
| Complex SQL queries | SQLite |
| Columnar analytics | Parquet/Arrow |
| Pure sequential iteration | HuggingFace Datasets |
| Maximum compression | Parquet |

---

## Reproduce Results

All benchmarks are in the repository:

```bash
# Clone
git clone https://github.com/zippydata/zippy
cd zippy

# Python
cd benchmarks/python && python benchmark_io.py

# Node.js
cd benchmarks/nodejs && npm install && node benchmark_io.js

# Rust
cd crates/zippy_core && cargo bench
```
