#!/usr/bin/env python3
"""Remote Dataset Loading Examples.

This script demonstrates loading ZDS datasets from remote sources:
- Loading from GitHub repositories
- Loading from GitLab and other Git hosts
- Caching and force download
- Working with private repositories
- Dataset info without downloading

Prerequisites:
    pip install gitpython  # for Git operations

Run: python examples/python/06_remote_datasets.py
"""

import sys
import os
from pathlib import Path

# Add parent to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

from zippy import (
    load_remote,
    dataset_info,
    clear_cache,
    ZDataset,
    ZDSStore,
)


def example_local_path():
    """Load dataset from local path."""
    print("=" * 60)
    print("Example 1: Load from Local Path")
    print("=" * 60)
    
    # First create a local dataset
    data_path = Path(__file__).parent.parent / "data" / "06_remote" / "local_demo"
    data_path.mkdir(parents=True, exist_ok=True)
    
    store = ZDSStore.open(str(data_path), collection="demo")
    store.put("doc1", {"text": "Local document 1", "value": 100})
    store.put("doc2", {"text": "Local document 2", "value": 200})
    
    # Load using load_remote (works with local paths too)
    dataset = load_remote(str(data_path), collection="demo")
    
    print(f"Loaded local dataset: {len(dataset)} documents")
    print(f"First document: {dataset[0]}")
    print(f"\nPath: {data_path}")


def example_github_format():
    """Demonstrate GitHub repository path formats."""
    print("\n" + "=" * 60)
    print("Example 2: GitHub Path Formats (Documentation)")
    print("=" * 60)
    
    print("""
ZDS supports various path formats for remote datasets:

1. GitHub (default host):
   - "username/repo"                    → github.com/username/repo
   - "username/repo@v1.0"               → specific tag/branch
   - "username/repo@main"               → main branch
   
2. Other Git hosts:
   - "gitlab.com/username/repo"         → GitLab
   - "bitbucket.org/username/repo"      → Bitbucket
   - "git.example.com/username/repo"    → Self-hosted
   
3. With subdirectory:
   load_remote("username/repo", subpath="data/dataset1")
   
4. With authentication:
   load_remote("username/private-repo", token="ghp_...")
   
5. Environment variables for tokens:
   - GITHUB_TOKEN: GitHub access
   - GITLAB_TOKEN: GitLab access
   - GIT_TOKEN: Generic Git token

Example usage:

    # Public GitHub repo
    dataset = load_remote("zippydata/example-datasets")
    
    # Specific version
    dataset = load_remote("zippydata/example-datasets@v1.0")
    
    # With collection
    train = load_remote("zippydata/example-datasets", collection="train")
    
    # Streaming mode (for large datasets)
    for doc in load_remote("zippydata/large-dataset", streaming=True):
        process(doc)
    
    # Private repo with token
    dataset = load_remote("myorg/private-data", token=os.environ["GITHUB_TOKEN"])
""")


def example_dataset_info_local():
    """Get dataset info without loading."""
    print("\n" + "=" * 60)
    print("Example 3: Dataset Info")
    print("=" * 60)
    
    # Create sample dataset
    data_path = Path(__file__).parent.parent / "data" / "06_remote" / "info_demo"
    data_path.mkdir(parents=True, exist_ok=True)
    
    # Create multiple collections
    for coll in ["train", "test", "validation"]:
        store = ZDSStore.open(str(data_path), collection=coll)
        for i in range(10 if coll == "train" else 5):
            store.put(f"doc_{i}", {"split": coll, "index": i})
    
    # Get info
    info = dataset_info(str(data_path))
    
    print(f"Dataset Info:")
    print(f"  Name: {info.name}")
    print(f"  Provider: {info.provider}")
    print(f"  URI: {info.uri}")
    print(f"  Description: {info.description}")
    
    # List collections
    from zippy import list_collections
    collections = list_collections(data_path)
    print(f"\nCollections: {collections}")
    
    for coll in collections:
        ds = ZDataset.from_store(str(data_path), collection=coll)
        print(f"  {coll}: {len(ds)} documents")


def example_caching():
    """Demonstrate caching behavior."""
    print("\n" + "=" * 60)
    print("Example 4: Caching Behavior")
    print("=" * 60)
    
    print("""
Remote datasets are cached locally for faster subsequent loads.

Cache location:
  - Default: ~/.cache/zds/
  - Override: ZDS_CACHE_DIR environment variable
  
Cache behavior:
  - First load: Downloads from remote
  - Subsequent loads: Uses cached version
  - Force refresh: load_remote(..., force_download=True)
  
Clear cache:
  from zippy import clear_cache
  
  # Clear all cached datasets
  clear_cache()
  
  # Clear specific dataset
  clear_cache("username/repo")
  
Example:

    # First load (downloads)
    dataset = load_remote("zippydata/example")  # Slow
    
    # Second load (cached)
    dataset = load_remote("zippydata/example")  # Fast
    
    # Force re-download
    dataset = load_remote("zippydata/example", force_download=True)
""")
    
    # Show cache directory
    cache_dir = Path(os.environ.get("ZDS_CACHE_DIR", Path.home() / ".cache" / "zds"))
    print(f"\nCache directory: {cache_dir}")
    if cache_dir.exists():
        print(f"Cache exists: Yes")
        # List cached datasets
        cached = list(cache_dir.glob("*"))
        if cached:
            print(f"Cached items: {len(cached)}")
    else:
        print(f"Cache exists: No (will be created on first remote load)")


def example_streaming_mode():
    """Demonstrate streaming mode for large datasets."""
    print("\n" + "=" * 60)
    print("Example 5: Streaming Mode")
    print("=" * 60)
    
    # Create a larger sample dataset
    data_path = Path(__file__).parent.parent / "data" / "06_remote" / "streaming_demo"
    data_path.mkdir(parents=True, exist_ok=True)
    
    store = ZDSStore.open(str(data_path), collection="large")
    for i in range(1000):
        store.put(f"doc_{i:06d}", {
            "id": i,
            "text": f"Document number {i}",
            "category": ["A", "B", "C"][i % 3],
        })
    
    print("Created dataset with 1000 documents")
    
    # Load in streaming mode
    print("\n>>> Streaming mode (memory efficient):")
    iterable = load_remote(str(data_path), collection="large", streaming=True)
    
    # Process without loading all into memory
    count = 0
    category_a = 0
    for doc in iterable:
        count += 1
        if doc["category"] == "A":
            category_a += 1
        if count >= 100:  # Stop early for demo
            break
    
    print(f"Processed {count} documents")
    print(f"Category A count: {category_a}")
    
    # Compare with regular mode
    print("\n>>> Regular mode (random access):")
    dataset = load_remote(str(data_path), collection="large", streaming=False)
    print(f"Dataset length: {len(dataset)}")
    print(f"Random access dataset[500]: {dataset[500]}")


def example_split_alias():
    """Demonstrate split parameter (HuggingFace compatibility)."""
    print("\n" + "=" * 60)
    print("Example 6: Split Parameter (HuggingFace Compatibility)")
    print("=" * 60)
    
    # Create dataset with train/test splits
    data_path = Path(__file__).parent.parent / "data" / "06_remote" / "splits_demo"
    data_path.mkdir(parents=True, exist_ok=True)
    
    for split in ["train", "test"]:
        store = ZDSStore.open(str(data_path), collection=split)
        count = 100 if split == "train" else 20
        for i in range(count):
            store.put(f"sample_{i}", {"split": split, "value": i})
    
    # Load using 'split' parameter (HuggingFace style)
    train = load_remote(str(data_path), split="train")
    test = load_remote(str(data_path), split="test")
    
    print(f"Train split: {len(train)} samples")
    print(f"Test split: {len(test)} samples")
    
    # 'split' is an alias for 'collection'
    train2 = load_remote(str(data_path), collection="train")
    print(f"\nUsing collection='train': {len(train2)} samples (same result)")


def main():
    """Run all examples."""
    print("ZDS Remote Dataset Loading Examples")
    print("=" * 60)
    print()
    
    example_local_path()
    example_github_format()
    example_dataset_info_local()
    example_caching()
    example_streaming_mode()
    example_split_alias()
    
    print("\n" + "=" * 60)
    print("All remote dataset examples completed!")
    print()
    print("Note: To test actual remote loading, you'll need:")
    print("  1. A ZDS dataset hosted on GitHub/GitLab")
    print("  2. Internet connection")
    print("  3. (Optional) Access token for private repos")
    print("=" * 60)


if __name__ == "__main__":
    main()
