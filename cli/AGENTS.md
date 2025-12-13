# cli/AGENTS.md

Consumer guide for the **`zippy` CLI**. Use this when you need to inspect, transform, or ship ZDS datasets from the terminal or inside shell pipelines.

## Install

```bash
cargo install --path cli   # from repo

# (coming soon) cargo install zippy-cli   # when published
```

The binary exposes `zippy <command> [options]`. Run `zippy --help` for a full list.

## Everyday Commands

| Command | Purpose |
|---------|---------|
| `zippy init <path> -c train` | Create a new store/collection |
| `zippy put <path> <doc_id> --data '{...}'` | Insert/update a document |
| `zippy get <path> <doc_id> --pretty` | Fetch a document |
| `zippy scan <path> -c train --jsonl` | Stream documents (great for `jq`) |
| `zippy stats <path>` | Show counts, strict-mode info, storage sizes |
| `zippy pack <path> archive.zds` | Create portable archive |
| `zippy unpack archive.zds ./out` | Restore archive |

All commands accept `-c/--collection` to target specific splits.

## Pipelines & Recipes

```bash
# Import JSONL into a store
cat data.jsonl | nl -ba | while read n line; do \
  echo "$line" | zippy put ./store -c train "doc_$n"; \
done

# Filter documents with jq
zippy scan ./store -c train --jsonl | jq 'select(.label == 1)'

# Backup daily snapshot
zippy pack ./store backups/store-$(date +%Y%m%d).zds

# Inspect stats in CI
zippy stats ./store --json | jq
```

## Options & Environment

| Flag / Env | Description |
|------------|-------------|
| `--strict` (on `init`) | Enforce single-schema writes |
| `--jsonl` (on `scan`) | Emit newline-delimited JSON for streaming |
| `ZDS_LOG=debug` | Enable verbose logs |
| `ZDS_CACHE_DIR` | Override cache directory for remote datasets |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Store not found` | Run `zippy init ./store -c train` first, or check path permissions |
| `Broken pipe` when piping | Add `set -o pipefail` in shell scripts; ensure consumer command handles EOF |
| Slow scans | Use `--jsonl` and stream to `jq`/`rg`; compact store if many tombstones |
| Need machine-readable output | Use `--json` (when available) or combine with `jq` |

## References

* CLI docs: [`docs/docs/cli.md`](../docs/docs/cli.md)
* Examples: `examples/cli/`
* Format spec: [`docs/docs/format.md`](../docs/docs/format.md)
* Programmatic APIs: Python (`zippy-data`), Node (`@zippydata/core`), Rust (`zippy_core`)
