#!/usr/bin/env python3
"""HuggingFace Integration Examples.

This script demonstrates ZDS integration with the HuggingFace ecosystem:
- Converting HuggingFace Dataset to ZDS format
- Converting ZDS to HuggingFace Dataset
- Using ZDS with HuggingFace DatasetDict
- Working with HuggingFace model training

Output is saved to: examples/data/05_huggingface/

Prerequisites:
    pip install datasets transformers

Run: python examples/python/05_huggingface_integration.py
"""

import sys
import shutil
from pathlib import Path

# Add parent to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

from zippy import (
    ZDSStore,
    ZDataset,
    from_hf,
    to_hf,
    to_hf_dict,
)

# Output directory for example data
DATA_DIR = Path(__file__).parent.parent / "data" / "05_huggingface"


def setup_data_dir():
    """Create/clean the data directory."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return str(DATA_DIR)


def check_hf_installed():
    """Check if HuggingFace datasets is installed."""
    try:
        import datasets
        return True
    except ImportError:
        print("=" * 60)
        print("HuggingFace `datasets` library not installed.")
        print("Install with: pip install datasets")
        print("=" * 60)
        return False


def example_create_sample_hf_dataset():
    """Create a sample HuggingFace dataset for demonstration."""
    from datasets import Dataset
    
    # Create a simple sentiment analysis dataset
    data = {
        "text": [
            "This movie was absolutely fantastic!",
            "Terrible waste of time, do not watch.",
            "Average film, nothing special.",
            "One of the best movies I've ever seen!",
            "Disappointing and boring throughout.",
            "A masterpiece of modern cinema.",
            "Not my cup of tea, but okay.",
            "Exceeded all my expectations!",
        ],
        "label": [1, 0, 1, 1, 0, 1, 0, 1],  # 1=positive, 0=negative
        "rating": [5, 1, 3, 5, 2, 5, 2, 5],
    }
    
    return Dataset.from_dict(data)


def example_hf_to_zds(data_path: str):
    """Convert HuggingFace Dataset to ZDS format."""
    print("=" * 60)
    print("Example 1: HuggingFace Dataset → ZDS")
    print("=" * 60)
    
    from datasets import Dataset
    
    # Create sample HF dataset
    hf_dataset = example_create_sample_hf_dataset()
    print(f"Created HuggingFace Dataset with {len(hf_dataset)} samples")
    print(f"Features: {hf_dataset.features}")
    
    # Convert to ZDS
    output_path = f"{data_path}/sentiment"
    zds = from_hf(hf_dataset, output_path, collection="reviews")
    
    print(f"\nConverted to ZDS: {len(zds)} documents")
    print(f"First document: {zds[0]}")
    print(f"\nData saved to: {output_path}/collections/reviews/")


def example_zds_to_hf(data_path: str):
    """Convert ZDS dataset back to HuggingFace format."""
    print("\n" + "=" * 60)
    print("Example 2: ZDS → HuggingFace Dataset")
    print("=" * 60)
    
    # Load ZDS and convert to HF
    zds = ZDataset.from_store(f"{data_path}/sentiment", collection="reviews")
    hf = to_hf(zds)
    
    print(f"Converted back to HuggingFace: {len(hf)} samples")
    print(f"Features: {hf.features}")
    print(f"\nSample row: {hf[0]}")
    
    # Demonstrate HF operations
    print("\n>>> HuggingFace Operations:")
    
    # Filter
    positive = hf.filter(lambda x: x["label"] == 1)
    print(f"Positive reviews: {len(positive)}")
    
    # Map
    def add_length(example):
        example["text_length"] = len(example["text"])
        return example
    
    with_length = hf.map(add_length)
    print(f"Added text_length field: {with_length[0]}")


def example_dataset_dict(data_path: str):
    """Work with HuggingFace DatasetDict (multiple splits)."""
    print("\n" + "=" * 60)
    print("Example 3: Multi-split Dataset (DatasetDict)")
    print("=" * 60)
    
    from datasets import Dataset, DatasetDict
    
    # Create train/test splits
    train_data = {
        "text": [
            "Great product, highly recommend!",
            "Terrible quality, broke immediately.",
            "Works as expected, good value.",
            "Best purchase I've made this year!",
            "Not worth the money at all.",
            "Exceeded my expectations completely.",
        ],
        "label": [1, 0, 1, 1, 0, 1],
    }
    
    test_data = {
        "text": [
            "Amazing quality and fast shipping!",
            "Worst purchase ever, avoid!",
        ],
        "label": [1, 0],
    }
    
    hf_dict = DatasetDict({
        "train": Dataset.from_dict(train_data),
        "test": Dataset.from_dict(test_data),
    })
    
    print(f"Created DatasetDict: {hf_dict}")
    
    # Convert to ZDS (each split becomes a collection)
    output_path = f"{data_path}/product_reviews"
    zds = from_hf(hf_dict, output_path)
    
    print(f"\nConverted to ZDS collections")
    
    # List collections
    from zippy import list_collections
    collections = list_collections(output_path)
    print(f"Collections: {collections}")
    
    # Load specific collection
    train_zds = ZDataset.from_store(output_path, collection="train")
    test_zds = ZDataset.from_store(output_path, collection="test")
    print(f"Train: {len(train_zds)} samples, Test: {len(test_zds)} samples")
    
    # Convert all collections back to DatasetDict
    hf_back = to_hf_dict(output_path)
    print(f"\nConverted back to DatasetDict: {hf_back}")
    print(f"\nData saved to: {output_path}/")


def example_custom_id_column(data_path: str):
    """Use custom ID column from HuggingFace dataset."""
    print("\n" + "=" * 60)
    print("Example 4: Custom ID Column")
    print("=" * 60)
    
    from datasets import Dataset
    
    # Dataset with explicit IDs
    data = {
        "article_id": ["news_001", "news_002", "news_003"],
        "title": [
            "Breaking: Major Discovery",
            "Tech Giants Report Earnings",
            "Weather Update for Weekend",
        ],
        "category": ["science", "business", "weather"],
    }
    
    hf = Dataset.from_dict(data)
    print(f"HF Dataset with article_id column: {hf[0]}")
    
    # Convert using article_id as doc ID
    output_path = f"{data_path}/news"
    zds = from_hf(hf, output_path, collection="articles", id_column="article_id")
    
    # Open store and verify IDs
    store = ZDSStore.open(output_path, collection="articles")
    print(f"\nZDS document IDs: {store.list_doc_ids()}")
    print(f"Get by ID: {store.get('news_001')}")
    print(f"\nData saved to: {output_path}/collections/articles/")


def example_training_workflow(data_path: str):
    """Simulate a training workflow with ZDS + HuggingFace."""
    print("\n" + "=" * 60)
    print("Example 5: Training Workflow Simulation")
    print("=" * 60)
    
    from datasets import Dataset
    
    # Create training data in ZDS format
    store = ZDSStore.open(f"{data_path}/training", collection="train")
    
    sentences = [
        ("The cat sat on the mat.", ["DET", "NOUN", "VERB", "ADP", "DET", "NOUN", "PUNCT"]),
        ("Dogs love to play fetch.", ["NOUN", "VERB", "PART", "VERB", "NOUN", "PUNCT"]),
        ("She wrote a beautiful poem.", ["PRON", "VERB", "DET", "ADJ", "NOUN", "PUNCT"]),
    ]
    
    for i, (text, tags) in enumerate(sentences):
        tokens = text.replace(".", " .").split()
        store.put(f"sent_{i:04d}", {
            "tokens": tokens,
            "pos_tags": tags,
        })
    
    print(f"Created ZDS training data: {len(store)} samples")
    
    # Convert to HuggingFace for training
    zds = ZDataset(store)
    hf = to_hf(zds)
    
    print(f"Converted to HF Dataset: {len(hf)} samples")
    print(f"Features: {hf.features}")
    
    # Simulate tokenization
    def tokenize(example):
        # In real use, you'd use a HuggingFace tokenizer
        example["input_ids"] = [hash(t) % 10000 for t in example["tokens"]]
        example["labels"] = [hash(t) % 17 for t in example["pos_tags"]]  # 17 POS tags
        return example
    
    tokenized = hf.map(tokenize)
    print(f"\nTokenized sample: {tokenized[0]}")
    
    # Demonstrate batching (for DataLoader)
    print("\n>>> Simulated training batches:")
    for i, batch in enumerate(tokenized.iter(batch_size=2)):
        print(f"Batch {i}: {len(batch['tokens'])} samples")
        if i >= 1:
            break
    
    print(f"\nData saved to: {data_path}/training/")


def example_large_dataset_streaming(data_path: str):
    """Demonstrate streaming for large datasets."""
    print("\n" + "=" * 60)
    print("Example 6: Streaming Large Datasets")
    print("=" * 60)
    
    from zippy import ZIterableDataset
    from zippy.fast_store import FastZDSStore
    
    # Create larger dataset
    store_path = f"{data_path}/large_streaming"
    store = FastZDSStore.open(store_path, collection="data")
    
    print("Creating 1000 samples...")
    for i in range(1000):
        store.put(f"doc_{i:06d}", {
            "id": i,
            "value": i * 1.5,
            "category": ["A", "B", "C"][i % 3],
        })
    store.flush()
    
    # Stream with ZIterableDataset
    iterable = ZIterableDataset(store)
    
    # Process in streaming fashion
    category_counts = {"A": 0, "B": 0, "C": 0}
    total = 0
    
    for doc in iterable:
        category_counts[doc["category"]] += 1
        total += 1
    
    print(f"Streamed {total} documents")
    print(f"Category counts: {category_counts}")
    
    # Convert subset to HuggingFace
    zds = ZDataset.from_store(store_path, collection="data")
    subset = zds.take(100)  # First 100
    hf_subset = to_hf(subset)
    
    print(f"\nConverted subset to HF: {len(hf_subset)} samples")
    print(f"\nData saved to: {store_path}/")


def main():
    """Run all examples."""
    if not check_hf_installed():
        # Run without HF examples - just create data
        print("\nRunning basic example without HuggingFace...")
        data_path = setup_data_dir()
        
        store = ZDSStore.open(f"{data_path}/basic", collection="demo")
        store.put("doc1", {"text": "Hello world", "label": 1})
        store.put("doc2", {"text": "Goodbye world", "label": 0})
        
        print(f"Created basic ZDS store: {len(store)} docs")
        print(f"Data saved to: {data_path}")
        print("\nInstall `datasets` to see HuggingFace integration examples.")
        return
    
    data_path = setup_data_dir()
    print(f"Output directory: {data_path}\n")
    
    example_hf_to_zds(data_path)
    example_zds_to_hf(data_path)
    example_dataset_dict(data_path)
    example_custom_id_column(data_path)
    example_training_workflow(data_path)
    example_large_dataset_streaming(data_path)
    
    print("\n" + "=" * 60)
    print("All HuggingFace examples completed successfully!")
    print(f"Data saved to: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
