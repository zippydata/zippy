---
layout: default
title: Python Guide
nav_order: 3
---

# Python Guide
{: .no_toc }

The Python SDK is the most feature-complete way to work with ZDS. It provides a familiar API for data scientists and ML engineers, with first-class support for HuggingFace, Pandas, and DuckDB.

<details open markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
1. TOC
{:toc}
</details>

---

## Installation

```bash
pip install zippy-data
```

Install with optional integrations based on your workflow:

```bash
# DataFrame support
pip install zippy-data[pandas]

# SQL queries with DuckDB
pip install zippy-data[duckdb]

# HuggingFace Dataset conversion
pip install zippy-data[hf]

# Everything
pip install zippy-data[all]
```

---

## Core Concepts

ZDS organizes data into **stores** and **collections**:

```
my_dataset/                    # Store (root directory)
├── collections/
│   ├── train/                 # Collection
│   │   └── meta/
│   │       ├── data.jsonl     # Your documents
│   │       └── index.bin      # O(1) lookup index
│   └── test/                  # Another collection
│       └── meta/
│           └── data.jsonl
```

- **Store**: A directory containing one or more collections
- **Collection**: A named group of documents (like `train`, `test`, `validation`)
- **Document**: A JSON object with a unique ID

---

## Working with Stores

### Opening a Store

```python
from zippy import ZDSStore

# Single collection (classic flow)
store = ZDSStore.open("./my_dataset", collection="train")
store.put("doc_001", {"text": "Hello world"})

# Multi-collection: omit the collection argument to get a root-capable handle
store = ZDSStore.open("./my_dataset", native=True)
train = store.collection("train")
evaluation = store.collection("evaluation")

train.put("doc_train", {"text": "Train sample"})
evaluation.put("doc_eval", {"text": "Eval sample"})

# Context manager for scoped writes
with ZDSStore.open("./my_dataset", "train") as scoped_store:
    scoped_store.put("doc_002", {"text": "Bye world"})

# Need low-level control (lock state, mode)? Grab the underlying root
native_root = store.root  # exposes NativeRoot / ZDSRoot
# This will close all the handles into this ZDS path so be careful!
native_root.close() 
```

> 💡 **When is `ZDSRoot` needed?** Most workflows can stick to `ZDSStore.open(...)`. Only reach for `store.root` when you need explicit read/write modes, manual locking, or to share the memoized root with other bindings.
>
> ⚠️ **Closing the root is destructive:** `store.root.close()` tears down the shared lock and invalidates every reader/writer for that path. Call it only during shutdown/cleanup, never in the middle of active work.

### Adding Documents

Every document needs a unique ID. The document itself can be any JSON-serializable dict:

```python
# Simple document
store.put("user_001", {
    "name": "Alice",
    "email": "alice@example.com"
})

# Complex nested structure
store.put("article_001", {
    "title": "Introduction to ZDS",
    "content": "ZDS is a human-readable document store...",
    "metadata": {
        "author": "Alice",
        "tags": ["tutorial", "beginner"],
        "published": True
    },
    "stats": {
        "views": 1542,
        "likes": 89
    }
})

# Schema-flexible: each document can have different fields
store.put("article_002", {
    "title": "Advanced ZDS Patterns",
    "content": "...",
    "metadata": {
        "author": "Bob",
        "tags": ["advanced"],
        "co_authors": ["Charlie", "Diana"]  # New field!
    }
})
```

### Retrieving Documents

```python
# Get by ID
doc = store.get("article_001")
print(doc["title"])  # "Introduction to ZDS"

# Dict-style access
doc = store["article_001"]

# Check if document exists
if "article_001" in store:
    print("Found!")

# Get with default (returns None if not found)
doc = store.get("nonexistent")  # Returns None
```

### Updating and Deleting

```python
# Update (put with same ID replaces the document)
store.put("user_001", {
    "name": "Alice",
    "email": "alice@newdomain.com",  # Updated
    "verified": True                  # New field
})

# Delete
store.delete("user_001")

# Bulk delete
for doc_id in ["temp_001", "temp_002", "temp_003"]:
    store.delete(doc_id)
```

### Scanning Documents

```python
# Iterate all documents
for doc in store.scan():
    print(doc["_id"], doc["title"])

# Project specific fields (more efficient for large documents)
for doc in store.scan(fields=["title", "metadata.author"]):
    print(doc)  # Only contains _id, title, and metadata.author

# Count documents
print(f"Total documents: {len(store)}")

# Get all document IDs
all_ids = store.list_doc_ids()
```

---

## ML Datasets

ZDS provides two dataset classes that mirror the HuggingFace Dataset API:

| Class | Use Case | Memory | Random Access |
|-------|----------|--------|---------------|
| `ZDataset` | Small-medium datasets | Loads index | Yes |
| `ZIterableDataset` | Large datasets | Streaming | No |

### ZDataset (Map-Style)

Best for datasets that fit in memory or when you need random access:

```python
from zippy import ZDataset

# Create from store path
dataset = ZDataset.from_store("./my_dataset", collection="train")

# Length and indexing
print(len(dataset))      # 10000
print(dataset[0])        # First document
print(dataset[-1])       # Last document
print(dataset[100:110])  # Slice (returns new ZDataset)
```

#### Transformations

All transformations return new datasets (immutable):

```python
# Shuffle with reproducible seed
shuffled = dataset.shuffle(seed=42)

# Filter documents
positive = dataset.filter(lambda x: x["label"] == 1)
long_texts = dataset.filter(lambda x: len(x["text"]) > 100)

# Transform documents
def preprocess(doc):
    return {
        **doc,
        "text_lower": doc["text"].lower(),
        "word_count": len(doc["text"].split())
    }

processed = dataset.map(preprocess)

# Select specific indices
subset = dataset.select([0, 10, 20, 30, 40])

# Take first N
sample = dataset.take(100)
```

#### Chaining Operations

```python
# Build a preprocessing pipeline
train_data = (
    dataset
    .filter(lambda x: x["quality_score"] > 0.8)
    .filter(lambda x: len(x["text"]) >= 50)
    .map(lambda x: {
        "text": x["text"].strip(),
        "label": x["category"],
        "source": x["metadata"]["source"]
    })
    .shuffle(seed=42)
)

print(f"Filtered to {len(train_data)} high-quality examples")
```

#### Batching for Training

```python
# Iterate in batches
for batch in dataset.batch(32):
    texts = [doc["text"] for doc in batch]
    labels = [doc["label"] for doc in batch]
    # Feed to your model...

# With PyTorch DataLoader
from torch.utils.data import DataLoader

loader = DataLoader(
    dataset,
    batch_size=32,
    shuffle=True,
    collate_fn=my_collate_fn
)
```

### ZIterableDataset (Streaming)

Best for large datasets that don't fit in memory:

```python
from zippy import ZIterableDataset

# Create streaming dataset
stream = ZIterableDataset.from_store("./large_dataset", "train")

# Iterate (no random access)
for doc in stream:
    process(doc)

# Shuffle with buffer (memory-efficient)
shuffled = stream.shuffle(buffer_size=10000, seed=42)

# Lazy transformations (applied during iteration)
processed = (
    stream
    .filter(lambda x: x["valid"])
    .map(lambda x: transform(x))
    .take(100000)  # Stop after 100k
)

# Batched streaming for training
for batch in stream.batch(32):
    train_step(batch)
```

---

## Recipes

### Recipe: LLM Fine-tuning Dataset

```python
from zippy import ZDSRoot, ZDataset

# Create training data root and collections
root = ZDSRoot.open("./finetune_data", native=True)
store = root.collection("conversations")

# Add conversation examples
store.put("conv_001", {
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is machine learning?"},
        {"role": "assistant", "content": "Machine learning is..."}
    ],
    "metadata": {"source": "manual", "quality": "high"}
})

# Convert to training format
dataset = ZDataset.from_store("./finetune_data", "conversations")

def to_chat_format(doc):
    """Convert to OpenAI chat format"""
    return {
        "messages": doc["messages"],
        "source": doc["metadata"]["source"]
    }

train_data = (
    dataset
    .filter(lambda x: x["metadata"]["quality"] == "high")
    .map(to_chat_format)
    .shuffle(seed=42)
)

# Export for training
for doc in train_data:
    print(doc)
```

### Recipe: Evaluation Pipeline

```python
from zippy import ZDSStore
import json
from datetime import datetime

# Store evaluation results across multiple runs
root = ZDSRoot.open("./eval_results", native=True)
store = root.collection("gpt4_baseline")

def run_evaluation(model, test_cases):
    for i, test in enumerate(test_cases):
        # Run model
        prediction = model.predict(test["input"])
        
        # Store result with full context
        store.put(f"eval_{i:05d}", {
            "input": test["input"],
            "expected": test["expected"],
            "prediction": prediction,
            "correct": prediction == test["expected"],
            "latency_ms": model.last_latency,
            "timestamp": datetime.now().isoformat(),
            "model_version": model.version
        })

# Later: analyze results
results = list(store.scan())
accuracy = sum(r["correct"] for r in results) / len(results)
avg_latency = sum(r["latency_ms"] for r in results) / len(results)

print(f"Accuracy: {accuracy:.2%}")
print(f"Avg latency: {avg_latency:.1f}ms")

# Debug failures
failures = [r for r in results if not r["correct"]]
for f in failures[:5]:
    print(f"Input: {f['input']}")
    print(f"Expected: {f['expected']}")
    print(f"Got: {f['prediction']}")
    print("---")
```

### Recipe: Synthetic Data Generation

```python
from zippy import ZDSStore
import openai

root = ZDSRoot.open("./synthetic_data", native=True)
store = root.collection("qa_pairs")

def generate_qa_pairs(topic, count=10):
    """Generate Q&A pairs using an LLM"""
    prompt = f"""Generate {count} question-answer pairs about {topic}.
    Format as JSON array with 'question' and 'answer' fields."""
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    pairs = json.loads(response.choices[0].message.content)
    
    for i, pair in enumerate(pairs):
        doc_id = f"{topic.replace(' ', '_')}_{i:03d}"
        store.put(doc_id, {
            "question": pair["question"],
            "answer": pair["answer"],
            "topic": topic,
            "generated_by": "gpt-4",
            "timestamp": datetime.now().isoformat()
        })

# Generate data for multiple topics
topics = ["Python programming", "Machine learning", "Data structures"]
for topic in topics:
    generate_qa_pairs(topic, count=20)

print(f"Generated {len(store)} Q&A pairs")

# Inspect the data (it's just JSONL!)
# cat ./synthetic_data/collections/qa_pairs/meta/data.jsonl | head -5 | jq .
```

---

## Integrations

### HuggingFace Datasets

Convert between ZDS and HuggingFace seamlessly:

```python
from datasets import load_dataset
from zippy import from_hf, to_hf

# HuggingFace → ZDS
hf_dataset = load_dataset("imdb", split="train")
zds = from_hf(hf_dataset, "./imdb_zds", collection="train")

# Now you can inspect with standard tools:
# cat ./imdb_zds/collections/train/meta/data.jsonl | head -1 | jq .

# ZDS → HuggingFace
hf_back = to_hf("./imdb_zds", collection="train")

# Works with DatasetDict too
hf_dict = load_dataset("imdb")  # Has train and test splits
from_hf(hf_dict, "./imdb_zds")  # Creates train/ and test/ collections
```

### Pandas DataFrames

```python
from zippy import read_zds, to_zds
import pandas as pd

# ZDS → DataFrame
df = read_zds("./my_dataset", collection="train")
print(df.head())

# DataFrame → ZDS
df = pd.DataFrame({
    "text": ["Hello", "World", "Test"],
    "label": [1, 0, 1],
    "score": [0.9, 0.3, 0.7]
})

# Use a column as document ID
to_zds(df, "./output", collection="data", id_column="text")

# Or auto-generate IDs
to_zds(df, "./output", collection="data")  # Uses row index
```

### DuckDB SQL Queries

Query your data with SQL:

```python
from zippy import query_zds, register_zds
import duckdb

# Quick one-off query
results = query_zds(
    "./my_dataset",
    """
    SELECT label, COUNT(*) as count, AVG(score) as avg_score
    FROM train
    GROUP BY label
    ORDER BY count DESC
    """
)
print(results)

# Complex queries with multiple collections
conn = duckdb.connect()
register_zds(conn, "./my_dataset", collection="train")
register_zds(conn, "./my_dataset", collection="metadata")

# Join across collections
results = conn.execute("""
    SELECT 
        t.text,
        t.label,
        m.category,
        m.source
    FROM train t
    JOIN metadata m ON t._id = m.doc_id
    WHERE t.score > 0.8
    ORDER BY t.score DESC
    LIMIT 100
""").fetchdf()
```

---

## API Reference

### ZDSStore

```python
class ZDSStore:
    @classmethod
    def open(cls, path: str, collection: str, strict: bool = False) -> ZDSStore:
        """Open or create a store."""
    
    def put(self, doc_id: str, document: dict) -> None:
        """Insert or update a document."""
    
    def get(self, doc_id: str) -> Optional[dict]:
        """Get document by ID. Returns None if not found."""
    
    def delete(self, doc_id: str) -> None:
        """Delete a document."""
    
    def scan(self, fields: List[str] = None) -> Iterator[dict]:
        """Iterate all documents, optionally projecting fields."""
    
    def list_doc_ids(self) -> List[str]:
        """Get all document IDs."""
    
    def __len__(self) -> int:
        """Number of documents."""
    
    def __contains__(self, doc_id: str) -> bool:
        """Check if document exists."""
    
    def __getitem__(self, doc_id: str) -> dict:
        """Dict-style access. Raises KeyError if not found."""
    
    def __setitem__(self, doc_id: str, document: dict) -> None:
        """Dict-style assignment."""
    
    def close(self) -> None:
        """Close the store."""
```

### ZDSRoot

```python
class ZDSRoot:
    @classmethod
    def open(cls, path: str, batch_size: int = 5000, native: bool = False) -> ZDSRoot:
        """Open or create a ZDS root. Initializes directories if needed."""

    def collection(self, name: str, batch_size: Optional[int] = None, strict: bool = False) -> ZDSStore:
        """Open (and lazily create) a collection under this root."""

    def list_collections(self) -> List[str]:
        """Return all collection names."""

    def collection_exists(self, name: str) -> bool:
        """Check if a collection already exists."""

    @property
    def root_path(self) -> Path:
        """Absolute path to the root directory."""

    @property
    def batch_size(self) -> int:
        """Default batch size used when opening collections."""
```

### ZDataset

```python
class ZDataset:
    @classmethod
    def from_store(cls, path: str, collection: str) -> ZDataset:
        """Create dataset from store path."""
    
    def __len__(self) -> int:
        """Number of documents."""
    
    def __getitem__(self, idx: Union[int, slice]) -> Union[dict, ZDataset]:
        """Index or slice access."""
    
    def shuffle(self, seed: int = None) -> ZDataset:
        """Return shuffled dataset."""
    
    def filter(self, fn: Callable[[dict], bool]) -> ZDataset:
        """Filter documents."""
    
    def map(self, fn: Callable[[dict], dict]) -> ZDataset:
        """Transform documents."""
    
    def select(self, indices: List[int]) -> ZDataset:
        """Select specific indices."""
    
    def take(self, n: int) -> ZDataset:
        """Take first n documents."""
    
    def batch(self, size: int) -> Iterator[List[dict]]:
        """Iterate in batches."""
    
    @property
    def features(self) -> dict:
        """Inferred schema from first document."""
```

---

## Next Steps

- **[Getting Started](./getting-started)** — 5-minute quickstart
- **[CLI Reference](./cli)** — Command-line tools
- **[Format Specification](./format)** — On-disk structure
- **[Examples](https://github.com/zippydata/zippy/tree/master/examples/python)** — Working code samples
