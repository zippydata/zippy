# crates/zippy_data/AGENTS.md

Consumer guide for the **`zippy_data` Rust crate**, the embeddable ZDS engine. Use this when you need maximum performance or want to integrate the format directly inside a Rust application/service.

## Install

```bash
cargo add zippy_data

# With optional serde helpers
cargo add serde_json
```

Requires Rust 1.75+. The crate is `no_std`? (no) – it targets std with mmap support.

## Quick Start

```rust
use zippy_data::{FastStore, Result};
use serde_json::json;

fn main() -> Result<()> {
    let mut store = FastStore::open("./data", "train", 1000)?;
    store.put("doc_001", json!({"text": "hello", "label": 1}))?;
    store.flush()?;

    let doc = store.get("doc_001")?;
    println!("{}", doc["text"]);
    Ok(())
}
```

### Key APIs

| Need | API |
|------|-----|
| Append JSONL fast | `FastStore::put` or `write_raw_jsonl` |
| Random lookups | `store.get(id)` or `Engine::get_document(id)` |
| Sequential scan with predicate | `Engine::scan(Some(&Predicate::eq("field", value)), None)` |
| File-per-doc access | `Engine` (reads `docs/` layout) |
| Pack/unpack | `zippy_data::container::{pack, unpack}` |

## Patterns

1. **Embedded ingestion service** – Use `FastStore` + `bulk_writer` for high-throughput writes and expose read-only `Engine` handles to worker threads.
2. **Analytics pipeline** – Convert external JSON into ZDS stores, then point DuckDB or Python bindings at the resulting directory.
3. **Offline packaging** – Use `FastStore` + `pack` to distribute `.zds` archives.

## Feature Notes

* `FastStore` uses append-only JSONL + binary index (O(1) access).
* `Engine` reads file-per-document layout (git-friendly) and supports projections/predicates.
* `Layout` helpers manage directory structure; always call `Layout::init_root` when creating fresh stores.

## Performance Tips

| Scenario | Tip |
|----------|-----|
| Write-heavy | Set batch size 1000+, call `flush()` before sharing store |
| Read-heavy | Keep `Engine` instances alive (avoid reopening); use projections to limit JSON parsing |
| Random access | Preload index via `FastStore::warm()` before serving requests |
| Large scans | Use `scan_raw` to get `Vec<Vec<u8>>` and parse with SIMD JSON of your choice |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Windows mmap errors | Ensure antivirus isn’t locking files; consider disabling indexing for the dataset folder |
| `rusqlite` build fails (benchmarks) | Install sqlite dev libs or disable default features when not benchmarking |
| High memory usage | Call `store.refresh_mmap()` after compaction or reopen store to release mmap |

## References

* Crate docs: `cargo doc --open -p zippy_data`
* Format spec: [`docs/docs/format.md`](../docs/docs/format.md)
* Benchmarks: [`BENCHMARK.md`](../../BENCHMARK.md)
* CLI companion: `zippy scan ./data -c train`
