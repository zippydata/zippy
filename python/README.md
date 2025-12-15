# Zippy (ZDS) Python Package

High-performance, HuggingFace-compatible dataset storage format.

## Installation

```bash
pip install zippy-zds

# With optional dependencies
pip install zippy-zds[pandas]
pip install zippy-zds[all]
```

## Quick Start

```python
from zippy import ZDSStore, ZDataset, ZIterableDataset

# Create a store
store = ZDSStore.open("./my_dataset", collection="train")

# Add documents
store.put("doc1", {"text": "Hello world", "label": 1})
store.put("doc2", {"text": "Goodbye world", "label": 0})

# Map-style dataset (random access)
dataset = store.to_dataset()
print(dataset[0])  # {"text": "Hello world", "label": 1}
print(len(dataset))  # 2

# Iterable dataset (streaming)
iterable = store.to_iterable_dataset()
for doc in iterable:
    print(doc)

# With shuffle buffer
for doc in iterable.shuffle(buffer_size=1000):
    print(doc)
```

## Multi-Collection Management with `ZDSStore`

```python
from zippy import ZDSStore

# Omit the collection argument to get a root-capable store handle
store = ZDSStore.open("./ml_data", native=True)

# Open as many collections as you need from the same handle
train = store.collection("train")
test = store.collection("test")
validation = store.collection("validation")

train.put("doc1", {"split": "train"})
test.put("doc1", {"split": "test"})
validation.put("doc1", {"split": "validation"})

print(store.list_collections())

# Context manager closes the shared root when you're done
with ZDSStore.open("./ml_data", "train") as store:
    store.put("doc2", {"split": "train"})

> ℹ️ `ZDSRoot` still exists under the hood (and is exposed via `store.root`)
> for advanced scenarios that need explicit read/write modes or manual
> locking, but most workflows can just rely on the unified
> `ZDSStore.open()` entry point shown above.
>
> ⚠️ Closing the root invalidates every reader/writer for that path. Only call `store.root.close()` during shutdown/cleanup.
print(store.list_collections())  # ['test', 'train', 'validation']
```

## DataFrame Integration

```python
from zippy import read_zds, to_zds

# Load as DataFrame (requires pandas)
df = read_zds("./my_dataset", collection="train")

# Export DataFrame to ZDS
to_zds(df, "./output", collection="exported")
```

## HuggingFace Compatibility

ZDS datasets are designed to work seamlessly with HuggingFace training loops:

```python
from zippy import ZIterableDataset

dataset = ZIterableDataset.from_store("./my_dataset", collection="train")

# Works with DataLoader
from torch.utils.data import DataLoader
loader = DataLoader(dataset, batch_size=32)
```
