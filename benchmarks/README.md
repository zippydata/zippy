# ZDS Benchmarks

Comprehensive benchmarks comparing ZDS against other data formats.

## Quick Start

```bash
# Run I/O benchmarks (10k records)
python benchmarks/python/benchmark_io.py -n 10000

# Run ML training benchmarks
python benchmarks/python/benchmark_ml.py -n 10000

# Save results to JSON
python benchmarks/python/benchmark_io.py -n 50000 -o benchmarks/results/io_50k.json
```

## Benchmark Suites

### I/O Performance (`benchmark_io.py`)

Compares read/write performance across formats:

| Format | Type | Best For |
|--------|------|----------|
| ZDS | Document store | Random access, crash safety, streaming |
| Pandas CSV | Columnar | Quick reads, tabular data |
| Pandas JSONL | Row-based | Nested data, streaming |
| Pandas Parquet | Columnar | Compression, column projection |
| Native JSON | Row-based | Simple serialization |
| HuggingFace Datasets | Arrow | Large datasets, memory mapping |

**Operations tested:**
- Write (ingestion)
- Read all (full scan)
- Random access (by ID)
- Filtered read (predicate pushdown)
- Projection read (column subset)

### ML Training (`benchmark_ml.py`)

Simulates ML training workloads:

- Sequential iteration
- Shuffled iteration
- Batched iteration (batch_size=32)
- Streaming shuffle (buffer=1000)
- Multi-epoch training simulation

## Interpreting Results

### ZDS Design Trade-offs

ZDS is optimized for:
- **Random access**: O(1) document retrieval by ID
- **Crash safety**: Append-only journal with atomic commits
- **Streaming**: Memory-efficient iteration
- **Flexibility**: Schema-per-document or strict mode

ZDS is not optimized for:
- **Bulk writes**: Individual file writes (slower than bulk formats)
- **Columnar operations**: Document-oriented, not columnar
- **Compression**: JSON storage (larger than Parquet)

### When to Use ZDS

✅ **Good fit:**
- Document-oriented data with stable IDs
- Random access patterns (key-value lookups)
- Crash-safe incremental updates
- Streaming/iterable dataset APIs
- Multi-language access (Rust, Python, DuckDB)

❌ **Consider alternatives:**
- Purely columnar analytics → Parquet
- Append-only logs → CSV/JSONL
- Read-heavy, rarely updated → Arrow/HF Datasets
- Compression critical → Parquet

## Python Benchmark Results

Results on Apple M3 Max (100,000 records):

| Approach | Write | Read All (cold) | Read All (warm) | Random (cold) | Random (warm) |
|----------|-------|-----------------|-----------------|---------------|---------------|
| **ZDS Native** | **4.66M** | 292k | **510k** | 7k | **308k** |
| SQLite | 237k | 267k | 263k | 89k | 88k |
| Pandas CSV | 205k | **957k** | *8.18M* | 8k | 227k |
| HF Datasets | 633k | 40k | 40k | 29k | 30k |

*Throughput in records/second. Pandas warm = in-memory DataFrame.*

### Key Findings (Python)
- **Write: ZDS is 20x faster** than SQLite
- **Random warm: ZDS is 3.5x faster** than SQLite (308k vs 88k)
- Cold includes index loading (~146ms for 100k entries)
- Pandas cold read wins for sequential scans (957k vs 292k)

### Running Python Benchmarks

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

## Node.js Benchmark Results

Results on Apple M3 Max (100,000 records):

| Approach | Write | Read All (cold) | Read All (warm) | Random (cold) | Random (warm) |
|----------|-------|-----------------|-----------------|---------------|---------------|
| **ZDS Native** | **4.26M** | 385k | **828k** | 6k | 201k |
| SQLite | 344k | **735k** | 650k | 147k | **263k** |
| LevelDB | 422k | 291k | 443k | 67k | 69k |

*Throughput in records/second.*

### Key Findings (Node.js)
- **Write: ZDS is 12x faster** than SQLite, 10x faster than LevelDB
- **Read warm: ZDS is 1.3x faster** than SQLite
- SQLite wins on cold random access (indexed queries)

### Running Node.js Benchmarks

```bash
cd benchmarks/nodejs
npm install

# Default: 100k records
node benchmark_io.js

# Custom size
node benchmark_io.js -n=500000
```

## Methodology

See [BENCHMARK.md](../BENCHMARK.md) for complete methodology including:
- Cold vs warm definitions
- Timing breakdown (open, scan, lookup)
- Test data generation
- Fairness considerations

## Rust Core Benchmarks

The Rust core library benchmarks measure raw engine performance and compare against SQLite and Sled.

### Results Summary (Apple M3 Max)

**Write Performance:**
| Records | ZDS | SQLite | Sled |
|---------|-----|--------|------|
| 1,000 | **8.5 ms** | 20 ms | 60 ms |
| 10,000 | **59 ms** | 163 ms | 114 ms |

**Read All (Warm):**
| Records | ZDS | SQLite | Sled |
|---------|-----|--------|------|
| 10,000 | 9.8 ms | **1.9 ms** | 1.9 ms |
| 100,000 | 95 ms | **20 ms** | 22 ms |

**Random Access (1000 lookups):**
| Store | Time | Throughput |
|-------|------|------------|
| ZDS | 2.0 ms | 505 K/s |
| SQLite | 2.2 ms | 453 K/s |
| Sled | **0.27 ms** | **3.6 M/s** |

### Running Rust Benchmarks

```bash
cd crates/zippy_core

# Run comparison benchmarks (ZDS vs SQLite vs Sled)
cargo bench --bench comparison

# Run ZDS-only benchmarks
cargo bench --bench ingestion
cargo bench --bench random_access
cargo bench --bench scan
```

### Benchmark Suites

| Suite | Description | Compares Against |
|-------|-------------|------------------|
| `comparison` | Full comparison | SQLite, Sled |
| `ingestion` | Write throughput | - |
| `random_access` | Point lookups | - |
| `scan` | Sequential reads | - |

### Key Findings

1. **ZDS is 2-3x faster for writes** than SQLite
2. **SQLite is 5-10x faster for reads** (optimized query engine)
3. **Random access is comparable** between ZDS and SQLite
4. **ZDS has lower cold-start penalty** than Sled

## CLI Benchmarks

Benchmark the CLI for shell scripting use cases:

```bash
# Build release binary
cargo build --release

# Use hyperfine for accurate benchmarks
hyperfine './target/release/zippy scan ./data -c train --jsonl > /dev/null'
hyperfine './target/release/zippy stats ./data'
```

## Dependencies

### Python
- Python 3.9+
- zippy package (`pip install -e python/`)
- Optional: pandas, pyarrow, datasets, orjson

### Node.js
- Node.js 18+
- better-sqlite3 (`npm install better-sqlite3`)
- classic-level (`npm install classic-level`)
