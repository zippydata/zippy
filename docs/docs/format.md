---
layout: default
title: Format Specification
nav_order: 7
---

# Format Specification

Technical specification for the ZDS (Zippy Data System) format.

## Overview

| Component | Format | Purpose |
|-----------|--------|---------|
| Container | Directory or ZIP | Packaging |
| Documents | JSONL | Data storage |
| Metadata | JSON | Self-description |
| Index | Binary (ZDX) | Fast lookups |

---

## Directory Structure

```
my_dataset/                         # Root (or .zds ZIP archive)
├── zds.json                        # Dataset metadata (optional)
└── collections/
    └── {collection_name}/          # e.g., "train", "test"
        ├── meta/
        │   ├── data.jsonl          # Documents (JSONL)
        │   ├── manifest.json       # Collection metadata
        │   └── index.bin           # Binary index (ZDX format)
        └── docs/                   # Alternative: file-per-document
            ├── doc_001.json
            └── doc_002.json
```

### Storage Modes

| Mode | Location | Use Case |
|------|----------|----------|
| **JSONL** | `meta/data.jsonl` | High performance, streaming |
| **File-per-doc** | `docs/*.json` | Git-friendly, manual editing |

Both modes can coexist. JSONL is preferred for performance.

---

## Document Format

Documents are stored as JSONL (JSON Lines). Each line is a valid JSON object with a required `_id` field.

### Requirements

- One JSON object per line
- UTF-8 encoding
- Lines terminated by `\n` (LF, byte `0x0A`)
- `_id` field required (string, unique within collection)
- Maximum recommended line size: 100MB

### Example

```jsonl
{"_id":"doc_001","text":"Hello world","score":0.95}
{"_id":"doc_002","text":"Goodbye","metadata":{"source":"api"}}
{"_id":"doc_003","text":"Test","nested":{"deep":{"value":42}}}
```

### Document ID Rules

- Must be non-empty string
- Allowed characters: `a-z`, `A-Z`, `0-9`, `_`, `-`, `.`
- Maximum length: 255 characters
- Must be unique within collection

---

## Metadata Schema

### Dataset Metadata (`zds.json`)

```json
{
  "$schema": "https://zippydata.org/schemas/zds/1.0.json",
  "version": "1.0",
  "name": "my_dataset",
  "description": "Optional description",
  "created": "2025-01-15T10:30:00Z",
  "modified": "2025-01-15T12:45:00Z",
  "collections": {
    "train": {"count": 50000},
    "test": {"count": 10000}
  }
}
```

### Collection Metadata (`manifest.json`)

```json
{
  "version": "0.1.0",
  "collection": "train",
  "strict": false,
  "created_at": "2025-01-15T10:30:00Z",
  "doc_count": 50000,
  "schema_count": 1
}
```

---

## Binary Index Format (ZDX)

The ZDX (Zippy Document indeX) format enables O(1) document lookup.

### File Layout

```
┌─────────────────────────────────────────────────────────┐
│ HEADER (16 bytes)                                       │
│ ┌────────────┬────────────┬────────────────────────────┐│
│ │   Magic    │  Version   │          Count             ││
│ │  "ZDSI"    │   u32 LE   │          u64 LE            ││
│ │  4 bytes   │  4 bytes   │          8 bytes           ││
│ └────────────┴────────────┴────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│ ENTRIES (variable length per entry)                     │
│                                                         │
│ For each entry:                                         │
│ ┌──────────────┬────────────────────────┬──────────────┐│
│ │  ID Length   │       Document ID      │    Entry     ││
│ │   u16 LE     │      [u8; id_len]      │   12 bytes   ││
│ └──────────────┴────────────────────────┴──────────────┘│
│                                                         │
│ Entry structure (12 bytes):                             │
│ ┌────────────────────────┬────────────────────────────┐ │
│ │        Offset          │         Length             │ │
│ │        u64 LE          │         u32 LE             │ │
│ │        8 bytes         │         4 bytes            │ │
│ └────────────────────────┴────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Header Fields

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0 | 4 | `u32` | `magic` | `0x5A445349` ("ZDSI") |
| 4 | 4 | `u32` | `version` | Format version (currently 1) |
| 8 | 8 | `u64` | `count` | Number of entries |

### Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `id_len` | `u16` | Length of document ID in bytes |
| `doc_id` | `[u8]` | UTF-8 document ID |
| `offset` | `u64` | Byte offset in JSONL file |
| `length` | `u32` | Byte length of JSON line |

### Design Rationale

| Decision | Benefit |
|----------|---------|
| Variable-length IDs | Efficient for short IDs |
| Little-endian | Native on x86/ARM64 |
| u64 offset | Support files > 4GB |
| u32 length | Sufficient for 4GB documents |

---

## Archive Format (.zds)

A `.zds` file is a standard ZIP archive containing the directory structure above.

### Compression

| Compression | Recommendation |
|-------------|----------------|
| STORE (none) | Fast read/write, larger size |
| DEFLATE | Smaller size, slower access |

For random access, STORE is preferred.

### Compatibility

```bash
# .zds files are standard ZIPs
unzip dataset.zds -d extracted/

# View contents
unzip -l dataset.zds

# Create manually
zip -r dataset.zds my_dataset/
```

---

## Interoperability

### Lock-in Freedom

ZDS uses only standard formats:
- **Container**: ZIP (universal)
- **Documents**: JSON (universal)
- **Text encoding**: UTF-8 (universal)
- **Line endings**: LF (universal)

If this library disappears, your data remains fully accessible with standard tools.

### Inspection

```bash
# View documents
cat my_dataset/collections/train/meta/data.jsonl | jq .

# Count documents
wc -l my_dataset/collections/train/meta/data.jsonl

# Search
grep "pattern" my_dataset/collections/train/meta/data.jsonl
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12 | Initial specification |

---

## Schema Reference

For JSON Schema definitions, see:

- [zds.json schema](https://zippydata.org/schemas/zds/1.0.json)
- [manifest.json schema](https://zippydata.org/schemas/manifest/1.0.json)
