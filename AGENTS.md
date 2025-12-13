# AGENTS.md

Zippy Data System (ZDS) offers multiple packages to **consume** the dataset format from different runtimes. This guide helps AI coding agents choose the right package, install it, and perform common data operations.

## Choose Your Surface

| Use Case | Package | Install | Guide |
|----------|---------|---------|-------|
| Python ML / data science | `zippy-data` | `pip install zippy-data[all]` | [python/AGENTS.md](python/AGENTS.md) |
| Node.js services / ETL | `@zippydata/core` | `npm install @zippydata/core` | [nodejs/AGENTS.md](nodejs/AGENTS.md) |
| Native Rust embedding | `zippy_core` | `cargo add zippy_core` | [crates/zippy_core/AGENTS.md](crates/zippy_core/AGENTS.md) |
| Shell / pipelines | `zippy` CLI | `cargo install --path cli` or download binary | [cli/AGENTS.md](cli/AGENTS.md) |

Each package exposes the same dataset layout (JSONL + index). Pick the runtime you need and follow its AGENT file for detailed usage snippets, troubleshooting, and advanced workflows.

## Universal Concepts

* **Stores** – A root directory with collections (train/test/etc.). All packages open stores via `path + collection`.
* **Human-readable** – Data stays JSON/JSONL, so you can inspect and edit with standard tools.
* **Cross-language** – You can write data in Python and read it in Node.js, CLI, or Rust without conversion.
* **Benchmarks** – See [`BENCHMARK.md`](BENCHMARK.md) for throughput numbers vs SQLite/Sled. Quote hardware specs when referencing data.
* **Format spec** – [`docs/docs/format.md`](docs/docs/format.md) documents the on-disk structure if you need low-level access.

## Typical Workflows

1. **Install package** using the commands above (prefer released artifacts over editing source).
2. **Create a store** – via Python `ZDSStore.open`, Node `ZdsStore.open`, Rust `FastStore::open`, or CLI `zippy init`.
3. **Ingest data** – put JSON documents, bulk write JSONL, or convert from Pandas/HF datasets.
4. **Query/scan** – use language-specific APIs (scan, list ids, stats) or CLI `zippy scan`.
5. **Share** – pack with CLI `zippy pack` or sync directories via git/rsync (format stays text).

## Where to Find Help

* **Python usage** – [python/AGENTS.md](python/AGENTS.md), [`docs/docs/python.md`](docs/docs/python.md), examples under `examples/python/`
* **Node.js usage** – [nodejs/AGENTS.md](nodejs/AGENTS.md), [`docs/docs/nodejs.md`](docs/docs/nodejs.md)
* **Rust embedding** – [crates/zippy_core/AGENTS.md](crates/zippy_core/AGENTS.md), [`PAPER.md`](PAPER.md)
* **CLI commands** – [cli/AGENTS.md](cli/AGENTS.md), [`docs/docs/cli.md`](docs/docs/cli.md)
* **Format + benchmarks** – [`docs/docs/format.md`](docs/docs/format.md), [`BENCHMARK.md`](BENCHMARK.md)
* **Security** – [`SECURITY.md`](SECURITY.md)

Need package-specific instructions? Jump into the linked AGENT file and follow the consumer-focused walkthroughs.
