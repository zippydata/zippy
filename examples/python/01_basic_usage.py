#!/usr/bin/env python3
"""Basic ZDS usage examples - store operations.

This script demonstrates core ZDS functionality:
- Creating and opening stores
- CRUD operations (put, get, delete)
- Scanning with predicates and projections
- Map-style and iterable dataset APIs
- Data persistence

Output is saved to: examples/data/01_basic/
"""

import sys
import shutil
from pathlib import Path

# Add parent to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

from zippy import ZDSStore, ZDataset, ZIterableDataset

# Output directory for example data
DATA_DIR = Path(__file__).parent.parent / "data" / "01_basic"


def setup_data_dir():
    """Create/clean the data directory."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return str(DATA_DIR)


def example_basic_store(data_path: str):
    """Basic store operations: put, get, delete, scan."""
    print("=" * 60)
    print("Example 1: Basic Store Operations")
    print("=" * 60)
    
    # Create a store
    store = ZDSStore.open(data_path, collection="users")
    
    # Put documents
    store.put("user_001", {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "age": 28,
        "tags": ["developer", "python"]
    })
    
    store.put("user_002", {
        "name": "Bob Jones",
        "email": "bob@example.com", 
        "age": 35,
        "tags": ["manager", "agile"]
    })
    
    store.put("user_003", {
        "name": "Charlie Brown",
        "email": "charlie@example.com",
        "age": 42,
        "tags": ["developer", "rust", "python"]
    })
    
    print(f"Store has {len(store)} documents")
    
    # Get a document
    user = store.get("user_001")
    print(f"Retrieved user_001: {user['name']}")
    
    # Check existence
    print(f"user_001 exists: {'user_001' in store}")
    print(f"user_999 exists: {'user_999' in store}")
    
    # List all IDs
    print(f"All IDs: {store.list_doc_ids()}")
    
    # Scan all documents
    print("\nAll users:")
    for doc in store.scan():
        print(f"  - {doc['name']} ({doc['email']})")
    
    # Scan with projection (only specific fields)
    print("\nNames only (projection):")
    for doc in store.scan(fields=["name"]):
        print(f"  - {doc}")
    
    # Scan with predicate
    print("\nDevelopers only (predicate):")
    for doc in store.scan(predicate={"tags": ["developer", "python"]}):
        print(f"  - {doc['name']}")
    
    # Delete a document
    store.delete("user_002")
    print(f"\nAfter delete: {len(store)} documents")
    
    # Dict-style access
    store["user_004"] = {"name": "Diana Prince", "email": "diana@example.com", "age": 30, "tags": []}
    print(f"Added user_004 via dict syntax: {store['user_004']['name']}")
    print(f"\nData saved to: {data_path}/collections/users/")


def example_strict_schema(data_path: str):
    """Strict schema mode - enforces consistent document structure."""
    print("\n" + "=" * 60)
    print("Example 2: Strict Schema Mode")
    print("=" * 60)
    
    # Create store with strict schema
    store = ZDSStore.open(data_path, collection="products", strict=True)
    
    # First document defines the schema
    store.put("prod_001", {
        "name": "Laptop",
        "price": 999.99,
        "in_stock": True
    })
    print("Added first product (defines schema)")
    
    # Same schema works
    store.put("prod_002", {
        "name": "Mouse",
        "price": 29.99,
        "in_stock": True
    })
    print("Added second product (same schema) ✓")
    
    # Different schema fails
    try:
        store.put("prod_003", {
            "title": "Keyboard",  # Different field name!
            "cost": 79.99
        })
    except ValueError as e:
        print(f"Schema mismatch caught: {e}")
    print(f"\nData saved to: {data_path}/collections/products/")


def example_dataset_api(data_path: str):
    """Map-style dataset API with transformations."""
    print("\n" + "=" * 60)
    print("Example 3: Dataset API (Map-style)")
    print("=" * 60)
    
    # Create and populate store
    store = ZDSStore.open(data_path, collection="sentences")
    
    sentences = [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is transforming every industry.",
        "Python is a versatile programming language.",
        "Data science requires both technical and domain expertise.",
        "Natural language processing enables text understanding.",
        "Deep learning models can learn complex patterns.",
        "The future of AI is both exciting and challenging.",
        "Good data quality is essential for model performance.",
    ]
    
    for i, text in enumerate(sentences):
        store.put(f"sent_{i:03d}", {
            "text": text,
            "word_count": len(text.split()),
            "char_count": len(text)
        })
    
    # Create dataset
    dataset = ZDataset(store)
    print(f"Dataset length: {len(dataset)}")
    
    # Index access
    print(f"First item: {dataset[0]['text'][:50]}...")
    print(f"Last item: {dataset[-1]['text'][:50]}...")
    
    # Slice
    subset = dataset[2:5]
    print(f"Slice [2:5]: {len(subset)} items")
    
    # Select specific indices
    selected = dataset.select([0, 3, 7])
    print(f"Selected [0,3,7]: {len(selected)} items")
    
    # Shuffle
    shuffled = dataset.shuffle(seed=42)
    print(f"Shuffled first item: {shuffled[0]['text'][:30]}...")
    
    # Map transformation
    def add_uppercase(doc):
        return {**doc, "text_upper": doc["text"].upper()}
    
    mapped = dataset.map(add_uppercase)
    print(f"Mapped has text_upper: {'text_upper' in mapped[0]}")
    
    # Filter
    long_sentences = dataset.filter(lambda x: x["word_count"] > 8)
    print(f"Long sentences (>8 words): {len(long_sentences)}")
    
    # Chained operations
    result = (
        dataset
        .filter(lambda x: x["word_count"] >= 7)
        .map(lambda x: {**x, "label": "long"})
        .shuffle(seed=123)
        .take(3)
    )
    print(f"Chained result: {len(result)} items")
    
    # Batching
    batches = list(dataset.batch(3))
    print(f"Batches of 3: {len(batches)} batches, last batch size: {len(batches[-1])}")
    
    # Features
    print(f"Features: {dataset.features}")
    print(f"\nData saved to: {data_path}/collections/sentences/")


def example_iterable_dataset(data_path: str):
    """Streaming dataset with shuffle buffer."""
    print("\n" + "=" * 60)
    print("Example 4: Iterable Dataset (Streaming)")
    print("=" * 60)
    
    # Create larger dataset
    store = ZDSStore.open(data_path, collection="logs")
    
    for i in range(100):
        store.put(f"log_{i:04d}", {
            "timestamp": f"2025-01-{(i % 28) + 1:02d}T{i % 24:02d}:00:00Z",
            "level": ["INFO", "WARN", "ERROR"][i % 3],
            "message": f"Log message number {i}",
            "request_id": f"req_{i:06d}"
        })
    
    # Create iterable dataset
    iterable = ZIterableDataset(store)
    
    # Count items (streaming)
    count = sum(1 for _ in iterable)
    print(f"Total items (streamed): {count}")
    
    # Shuffle with buffer
    shuffled = iterable.shuffle(buffer_size=20, seed=42)
    first_5 = list(shuffled.take(5))
    print(f"First 5 after shuffle: {[d['message'][-2:] for d in first_5]}")
    
    # Filter and map (lazy)
    errors = (
        iterable
        .filter(lambda x: x["level"] == "ERROR")
        .map(lambda x: {**x, "severity": "high"})
    )
    error_count = sum(1 for _ in errors)
    print(f"Error logs: {error_count}")
    
    # Batched iteration
    batch_count = 0
    for batch in iterable.batch(25):
        batch_count += 1
    print(f"Batches of 25: {batch_count}")
    print(f"\nData saved to: {data_path}/collections/logs/")


def example_persistence(data_path: str):
    """Data persistence across sessions."""
    print("\n" + "=" * 60)
    print("Example 5: Persistence")
    print("=" * 60)
    
    # Session 1: Create and populate
    store1 = ZDSStore.open(data_path, collection="persist_test")
    store1.put("doc1", {"value": 100})
    store1.put("doc2", {"value": 200})
    print(f"Session 1: Added {len(store1)} documents")
    
    # Close (just let it go out of scope)
    del store1
    
    # Session 2: Reopen and verify
    store2 = ZDSStore.open(data_path, collection="persist_test")
    print(f"Session 2: Found {len(store2)} documents")
    print(f"  doc1 value: {store2.get('doc1')['value']}")
    print(f"  doc2 value: {store2.get('doc2')['value']}")
    
    # Add more
    store2.put("doc3", {"value": 300})
    print(f"Session 2: Now {len(store2)} documents")
    print(f"\nData saved to: {data_path}/collections/persist_test/")


def main():
    """Run all examples."""
    data_path = setup_data_dir()
    print(f"Output directory: {data_path}\n")
    
    example_basic_store(data_path)
    example_strict_schema(data_path)
    example_dataset_api(data_path)
    example_iterable_dataset(data_path)
    example_persistence(data_path)
    
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print(f"Data saved to: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
