---
layout: default
title: CLI Reference
nav_order: 6
---

# CLI Reference
{: .no_toc }

The `zippy` command-line tool lets you create, inspect, and manage ZDS datasets without writing code. It's perfect for shell scripts, data pipelines, and quick exploration.

<details open markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
1. TOC
{:toc}
</details>

---

## Installation

### From Pre-built Binaries

Download from the [releases page](https://github.com/zippydata/zippy/releases):

```bash
# macOS (Apple Silicon)
curl -L https://github.com/zippydata/zippy/releases/latest/download/zippy-aarch64-apple-darwin.tar.gz | tar xz
sudo mv zippy /usr/local/bin/

# macOS (Intel)
curl -L https://github.com/zippydata/zippy/releases/latest/download/zippy-x86_64-apple-darwin.tar.gz | tar xz
sudo mv zippy /usr/local/bin/

# Linux (x64)
curl -L https://github.com/zippydata/zippy/releases/latest/download/zippy-x86_64-unknown-linux-gnu.tar.gz | tar xz
sudo mv zippy /usr/local/bin/
```

### From Source

```bash
# With Cargo
cargo install --path cli

# Or build locally
cargo build --release -p zippy-cli
./target/release/zippy --help
```

---

## Quick Start

```bash
# Create a new dataset
zippy init ./my_dataset -c train

# Add some documents
zippy put ./my_dataset -c train doc_001 --data '{"text": "Hello world", "label": 1}'
zippy put ./my_dataset -c train doc_002 --data '{"text": "Goodbye", "label": 0}'

# View a document
zippy get ./my_dataset -c train doc_001 --pretty

# List all documents
zippy scan ./my_dataset -c train

# Check statistics
zippy stats ./my_dataset

# Package for sharing
zippy pack ./my_dataset dataset.zds
```

---

## Commands

### init

Create a new ZDS store with an optional initial collection.

```bash
zippy init <path> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Initial collection name (default: `default`) |
| `--strict` | Enable strict schema mode |

**Examples:**

```bash
# Basic initialization
zippy init ./my_dataset

# With named collection
zippy init ./my_dataset -c train

# Strict mode (all documents must match first document's schema)
zippy init ./my_dataset -c products --strict
```

---

### put

Add or update a document in a collection.

```bash
zippy put <path> <doc_id> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Collection name (default: `default`) |
| `--data <json>` | JSON document inline |

If `--data` is not provided, reads JSON from stdin.

**Examples:**

```bash
# Inline JSON
zippy put ./data -c users user_001 --data '{"name": "Alice", "role": "admin"}'

# From stdin
echo '{"name": "Bob", "role": "user"}' | zippy put ./data -c users user_002

# From file
cat user.json | zippy put ./data -c users user_003

# Complex document
zippy put ./data -c orders order_001 --data '{
  "customer": "cust_123",
  "items": [{"sku": "WIDGET", "qty": 2}],
  "total": 59.98
}'
```

---

### get

Retrieve a document by ID.

```bash
zippy get <path> <doc_id> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Collection name (default: `default`) |
| `--pretty` | Pretty-print JSON output |

**Examples:**

```bash
# Compact output
zippy get ./data -c users user_001
# {"name":"Alice","role":"admin"}

# Pretty-printed
zippy get ./data -c users user_001 --pretty
# {
#   "name": "Alice",
#   "role": "admin"
# }

# Pipe to jq for processing
zippy get ./data -c users user_001 | jq '.name'
# "Alice"
```

---

### delete

Remove a document from a collection.

```bash
zippy delete <path> <doc_id> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Collection name (default: `default`) |

**Example:**

```bash
zippy delete ./data -c users user_001
```

---

### scan

List and output documents from a collection.

```bash
zippy scan <path> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Collection name (default: `default`) |
| `-l, --limit <n>` | Maximum documents to output |
| `--fields <list>` | Comma-separated fields to project |
| `--jsonl` | Output as JSON Lines (one per line) |

**Examples:**

```bash
# All documents (pretty array)
zippy scan ./data -c users

# First 10 documents
zippy scan ./data -c users -l 10

# Only specific fields
zippy scan ./data -c users --fields name,email

# JSONL format (best for piping)
zippy scan ./data -c users --jsonl

# Combine with jq
zippy scan ./data -c users --jsonl | jq 'select(.role == "admin")'
```

---

### list

Show all collections in a store.

```bash
zippy list <path>
```

**Example:**

```bash
zippy list ./data
# Collections:
#   users     (150 documents)
#   products  (89 documents)
#   orders    (1,247 documents)
```

---

### stats

Display statistics about a store or collection.

```bash
zippy stats <path> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Specific collection (shows all if omitted) |
| `--json` | Output as JSON |

**Examples:**

```bash
# Overview of all collections
zippy stats ./data
# Store: ./data
# Total collections: 3
# Total documents: 1,486
#
# Collection    Documents    Size
# users         150          45 KB
# products      89           23 KB
# orders        1,247        892 KB

# Specific collection
zippy stats ./data -c users

# Machine-readable JSON
zippy stats ./data --json | jq '.collections[].count'
```

---

### validate

Check store integrity and optionally repair indexes.

```bash
zippy validate <path> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Collection to validate (all if omitted) |
| `--fix` | Rebuild indexes if invalid |

**Examples:**

```bash
# Check all collections
zippy validate ./data
# ✓ users: valid (150 documents, index OK)
# ✓ products: valid (89 documents, index OK)

# Fix corrupted indexes
zippy validate ./data --fix
```

---

### reindex

Rebuild the binary index from JSONL data.

```bash
zippy reindex <path> [options]
```

| Option | Description |
|--------|-------------|
| `-c, --collection <name>` | Collection name (default: `default`) |

**Example:**

```bash
zippy reindex ./data -c users
# Reindexed 150 documents in 12ms
```

---

### pack

Create a portable `.zds` archive from a store.

```bash
zippy pack <source> <dest>
```

The archive is a standard ZIP file that anyone can extract without ZDS tools.

**Examples:**

```bash
# Create archive
zippy pack ./my_dataset ./my_dataset.zds

# With timestamp
zippy pack ./data "backup_$(date +%Y%m%d_%H%M%S).zds"
```

---

### unpack

Extract a `.zds` archive to a directory.

```bash
zippy unpack <source> <dest>
```

**Examples:**

```bash
# Extract with zippy
zippy unpack ./dataset.zds ./extracted

# Or use standard unzip (it's just a ZIP file!)
unzip ./dataset.zds -d ./extracted
```

---

## Recipes

### Import JSONL File

```bash
# Fast: use the bulk import (if available)
zippy import ./data -c train < data.jsonl

# Manual: loop through lines
i=0
while IFS= read -r line; do
    echo "$line" | zippy put ./data -c import "doc_$(printf '%06d' $i)"
    ((i++))
done < data.jsonl
echo "Imported $i documents"
```

### Export to JSONL

```bash
# Export entire collection
zippy scan ./data -c train --jsonl > train.jsonl

# Export with filtering
zippy scan ./data -c train --jsonl | jq 'select(.score > 0.8)' > high_score.jsonl
```

### Data Exploration with jq

```bash
# Count documents by label
zippy scan ./data -c train --jsonl | jq -s 'group_by(.label) | map({label: .[0].label, count: length})'

# Find unique values
zippy scan ./data -c train --jsonl | jq -s '[.[].category] | unique'

# Sample random documents
zippy scan ./data -c train --jsonl | shuf | head -5 | jq .

# Calculate statistics
zippy scan ./data -c train --jsonl | jq -s '{
  count: length,
  avg_score: (map(.score) | add / length),
  max_score: (map(.score) | max)
}'
```

### Backup and Restore

```bash
# Daily backup
zippy pack ./production "backups/prod_$(date +%Y%m%d).zds"

# Restore from backup
zippy unpack backups/prod_20241201.zds ./restored

# Verify restoration
zippy stats ./restored
```

### Cross-Platform Sharing

```bash
# Create portable archive
zippy pack ./my_dataset dataset.zds

# Share via any method (email, S3, etc.)
aws s3 cp dataset.zds s3://my-bucket/datasets/

# Recipients can use without installing ZDS
unzip dataset.zds -d extracted/
cat extracted/collections/train/meta/data.jsonl | head -5 | jq .
```

### Pipeline Integration

```bash
# Generate data with Python, store with CLI
python generate_data.py | while IFS= read -r line; do
    id=$(echo "$line" | jq -r '._id')
    echo "$line" | zippy put ./output -c generated "$id"
done

# Process with CLI, analyze with Python
zippy scan ./data -c results --jsonl | python analyze.py
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ZDS_CACHE_DIR` | Cache directory for remote datasets | `~/.cache/zds` |
| `RUST_LOG` | Log level (`debug`, `info`, `warn`, `error`) | `warn` |

**Example:**

```bash
# Enable debug logging
RUST_LOG=debug zippy scan ./data -c train

# Custom cache directory
ZDS_CACHE_DIR=/tmp/zds-cache zippy get remote://...
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (file not found, invalid data, etc.) |
| `2` | Invalid arguments or usage |

---

## Next Steps

- **[Getting Started](./getting-started)** — 5-minute quickstart
- **[Python Guide](./python)** — Python SDK for programmatic access
- **[Format Specification](./format)** — On-disk structure details
- **[Examples](https://github.com/zippydata/zippy/tree/master/examples/cli)** — Shell script examples
