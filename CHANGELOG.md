# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-12-15

### Added

#### Core Features
- **ZDSRoot**: Root-level store handle for managing multiple collections safely
  - `ZDSRoot::open(path, batch_size, mode)` creates/opens a ZDS root directory
  - `root.collection(name)` returns a store handle for a specific collection
  - `root.list_collections()` lists all collections in the root
  - `root.collection_exists(name)` checks if a collection exists
  - Enables writing to multiple collections without corruption

- **Read/Write Modes**: Open stores in read-only or read-write mode
  - `OpenMode::Read` - no locking, multiple readers allowed
  - `OpenMode::ReadWrite` - exclusive write lock, safe concurrent access

- **File Locking**: Exclusive write locks prevent multi-process corruption
  - Uses flock + explicit lock file for cross-platform support
  - Lock file includes PID, hostname, timestamp for debugging
  - Automatic cleanup on process exit or crash

- **Root Memoization**: Same-path opens return shared instance
  - Prevents accidental multiple writers to same store
  - Cache keyed by (canonical_path, mode)

#### Python Package (`zippy-data`)
- `ZDSRoot`: High-level root handle class
  - `ZDSRoot.open(path, native=True, mode="rw")` for native Rust backend
  - `root.mode` / `root.is_writable` properties
  - `root.close()` to release locks
  - Context manager support (`with ZDSRoot.open(...) as root:`)
  - Pure Python fallback when native unavailable
- `NativeRoot`: Native Rust bindings for root-level operations

#### Node.js Package (`@zippydata/core`)
- `ZdsRoot`: Native Rust root handle class
  - `ZdsRoot.open(path, batchSize?, mode?)` factory method
  - `root.collection(name, batchSize?)` returns store handle
  - `root.mode` / `root.isWritable` getters
  - `root.close()` method to release locks
  - `root.info` getter for root metadata (now includes mode)

### Changed
- Renamed native Python module from `_core` to `_zippy_data` for consistency
- `ZDSRoot::open()` now requires explicit mode parameter in Rust

## [0.1.0] - 2025-12-13

### Added

#### Core Features
- **ZDS Format**: Human-readable document storage using JSONL + ZIP container
- **ZDX Index**: Binary index format for O(1) document lookups
- **Schema Flexibility**: Per-document schemas, no migrations required
- **Multi-Collection Support**: Organize data into named collections

#### Python Package (`zippy-data`)
- `load_remote()`: Load datasets from remote git repositories or cloud storage
- `ZDSStore`: Low-level key-value store interface
- `FastZDSStore`: High-performance native Rust-backed store
- `ZDataset`: HuggingFace-compatible map-style dataset
- `ZIterableDataset`: Streaming dataset with shuffle buffer
- `read_zds()` / `to_zds()`: Pandas DataFrame integration
- `query_zds()`: DuckDB SQL integration
- **Remote Providers**: GitHub provider implemented, S3/GCS/Azure stubs

#### Node.js Package (`@zippydata/core`)
- `ZdsStore`: Native Rust bindings via napi-rs
- `writeJsonl()`: High-throughput bulk writes
- `readJsonlBlob()`: Zero-copy bulk reads
- Random access by document ID
- Full scan iteration

#### Rust Crate (`zippy-data`)
- `FastStore`: Memory-mapped JSONL with FxHashMap index
- SIMD-accelerated JSON parsing (simd-json)
- SIMD newline search (memchr)
- Benchmark suite (criterion)

#### Integrations
- **DuckDB**: SQL queries on ZDS collections
- **Pandas**: `read_zds()` and `to_zds()` functions
- **HuggingFace**: Compatible dataset API (map-style and iterable)

#### Tools
- VSCode extension for visual editing
- CLI tool for dataset management

#### Documentation
- Technical paper (PAPER.md) with format specification
- Benchmark methodology (BENCHMARK.md)
- Release process (RELEASE.md)

### Performance

Benchmarks on Apple M3 Max with 100k records:

| Operation | ZDS Native | SQLite | Speedup |
|-----------|------------|--------|---------|
| Write | 4.66M rec/s | 237k rec/s | **20x** |
| Read All (warm) | 510k rec/s | 263k rec/s | **1.9x** |
| Random Access (warm) | 308k rec/s | 88k rec/s | **3.5x** |

### Notes

This is the initial public release. The format is stable for v1.x but may evolve
in future major versions. Feedback welcome via GitHub issues.

---

[Unreleased]: https://github.com/zippydata/zippy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zippydata/zippy/releases/tag/v0.1.0
