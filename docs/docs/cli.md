---
layout: default
title: CLI Reference
parent: Documentation
nav_order: 5
---

# CLI Reference

The `zippy` command-line tool for managing ZDS datasets.

## Installation

```bash
# From source
cargo install --path cli

# Or build locally
cargo build --release
./target/release/zippy --help
```

## Commands

### init

Initialize a new ZDS store.

```bash
zippy init <path> [options]

Options:
  -c, --collection <name>   Initial collection name (default: "default")
  --strict                  Enable strict schema mode
```

**Examples:**
```bash
zippy init ./my_dataset
zippy init ./my_dataset -c train
zippy init ./my_dataset -c products --strict
```

---

### put

Add or update a document.

```bash
zippy put <path> <doc_id> [options]

Options:
  -c, --collection <name>   Collection name (default: "default")
  --data <json>             JSON document (reads from stdin if not provided)
```

**Examples:**
```bash
# Inline JSON
zippy put ./data -c users user_001 --data '{"name": "Alice", "age": 30}'

# From stdin
echo '{"name": "Bob", "age": 25}' | zippy put ./data -c users user_002

# From file
cat user.json | zippy put ./data -c users user_003
```

---

### get

Retrieve a document by ID.

```bash
zippy get <path> <doc_id> [options]

Options:
  -c, --collection <name>   Collection name (default: "default")
  --pretty                  Pretty-print JSON output
```

**Examples:**
```bash
zippy get ./data -c users user_001
zippy get ./data -c users user_001 --pretty
```

---

### delete

Delete a document.

```bash
zippy delete <path> <doc_id> [options]

Options:
  -c, --collection <name>   Collection name (default: "default")
```

**Examples:**
```bash
zippy delete ./data -c users user_001
```

---

### scan

Scan and output documents.

```bash
zippy scan <path> [options]

Options:
  -c, --collection <name>   Collection name (default: "default")
  -l, --limit <n>           Maximum documents to output
  --fields <list>           Comma-separated fields to project
  --jsonl                   Output as JSON Lines (one per line)
```

**Examples:**
```bash
# All documents
zippy scan ./data -c users

# First 10
zippy scan ./data -c users -l 10

# Specific fields
zippy scan ./data -c users --fields name,email

# JSONL format (for piping)
zippy scan ./data -c users --jsonl | jq '.name'
```

---

### list

List collections in a store.

```bash
zippy list <path>
```

**Example:**
```bash
zippy list ./data
# Collections:
#   users (150 documents)
#   products (89 documents)
```

---

### stats

Show statistics for a store.

```bash
zippy stats <path> [options]

Options:
  -c, --collection <name>   Specific collection (shows all if omitted)
  --json                    Output as JSON
```

**Examples:**
```bash
zippy stats ./data
zippy stats ./data -c users
zippy stats ./data --json
```

---

### validate

Validate store structure and indexes.

```bash
zippy validate <path> [options]

Options:
  -c, --collection <name>   Collection to validate (all if omitted)
  --fix                     Rebuild indexes if invalid
```

**Examples:**
```bash
zippy validate ./data
zippy validate ./data --fix
```

---

### reindex

Rebuild indexes from disk.

```bash
zippy reindex <path> [options]

Options:
  -c, --collection <name>   Collection name (default: "default")
```

**Example:**
```bash
zippy reindex ./data -c users
```

---

### pack

Pack a store into a .zds archive.

```bash
zippy pack <source> <dest>
```

**Example:**
```bash
zippy pack ./my_dataset ./my_dataset.zds
```

---

### unpack

Unpack a .zds archive.

```bash
zippy unpack <source> <dest>
```

**Example:**
```bash
zippy unpack ./my_dataset.zds ./extracted
```

---

## Pipeline Examples

### Import from JSONL file

```bash
# Each line becomes a document
i=0
while read -r line; do
    echo "$line" | zippy put ./data -c import "doc_$i"
    i=$((i + 1))
done < data.jsonl
```

### Export to JSONL

```bash
zippy scan ./data -c users --jsonl > users.jsonl
```

### Filter with jq

```bash
zippy scan ./data -c users --jsonl | jq 'select(.age > 30)'
```

### Backup with timestamp

```bash
zippy pack ./data "backup_$(date +%Y%m%d).zds"
```

### Cross-platform data sharing

```bash
# Create portable archive
zippy pack ./my_dataset dataset.zds

# Recipients can unzip without zippy
unzip dataset.zds -d extracted/
cat extracted/collections/train/meta/data.jsonl | head
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ZDS_CACHE_DIR` | Cache directory for remote datasets |
| `RUST_LOG` | Log level (debug, info, warn, error) |
