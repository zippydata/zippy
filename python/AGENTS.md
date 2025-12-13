# python/AGENTS.md

Consumer guide for the **Zippy Data System (ZDS) Python package**. Use this to ingest, transform, and ship datasets from Python code.

## Install

```bash
pip install zippy-data[all]

# Minimal footprint
pip install zippy-data

# Optional extras
pip install zippy-data[pandas]
pip install zippy-data[duckdb]
pip install zippy-data[hf]
```

The package bundles the native engine—no compilation required.

## Quick Start

```python
from zippy import ZDSStore

store = ZDSStore.open("./my_store", collection="train")
store.put("doc_001", {"text": "hello", "label": 1})

print(store.get("doc_001"))
print(len(store))
for doc in store.scan():
    ...
```

### Frequently Needed Snippets

| Task | Code |
|------|------|
| Bulk import JSONL | `store.write_jsonl(Path("data.jsonl").read_bytes(), ids)` |
| Random-access dataset | `from zippy import ZDataset; ds = ZDataset.from_store("./my_store", "train")` |
| Streaming dataset | `from zippy import ZIterableDataset; ds = ZIterableDataset.from_store(...)` |
| Pandas interop | `df = read_zds("./my_store", "train"); to_zds(df, "./out")` |
| HuggingFace interop | `from_hf(dataset, "./store")`, `to_hf_dict("./store")` |
| DuckDB query | `query_zds("./my_store", "SELECT label, count(*) FROM train GROUP BY label")` |
| Remote dataset | `load_remote("zippydata/example-datasets", collection="train")` |

## Typical Workflow

1. **Create or open** a store with `ZDSStore.open(path, collection)`.
2. **Write data** using `put`, `write_jsonl`, or conversion helpers (`from_hf`, `to_zds`).
3. **Consume** through `ZDataset` (random access) or `ZIterableDataset` (streaming/batching).
4. **Analyze/export** via Pandas, DuckDB, or HuggingFace conversions.
5. **Distribute** with the CLI (`zippy pack ./my_store ./archive.zds`) or by sharing the directory.

## Integrations & Recipes

| Need | Recipe |
|------|--------|
| PyTorch training | Wrap `ZDataset` or `ZIterableDataset` in a `DataLoader` |
| HF Dataset push | `to_hf_dict("./my_store")` and upload via HF Hub APIs |
| Feature engineering | Load as Pandas (`read_zds`) → transform → `to_zds` |
| SQL analytics | Use `query_zds` or register collections via `register_zds(conn, path, collection)` |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ImportError: cannot import name '_core'` | Reinstall: `pip install --force-reinstall zippy-data` |
| Slow writes | Use `store.bulk_writer(batch_size=1000)` or `write_jsonl` |
| Mixed schema errors | Open with `strict=False` or normalize documents before writing |
| Need remote data | `load_remote("org/dataset", token=...)` supports Git, HTTP, local paths |

## References

* API reference: [`docs/docs/python.md`](../docs/docs/python.md)
* Examples: `examples/python/`
* Format spec: [`docs/docs/format.md`](../docs/docs/format.md)
* CLI companion: `zippy scan ./my_store -c train`
