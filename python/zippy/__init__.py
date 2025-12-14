"""
ZDS (Zippy Data System) - High-performance dataset storage format.

This package provides Python bindings for ZDS, a multi-language dataset
storage format with native support for HuggingFace-style datasets.

Main components:
- load_remote: Load datasets from Git repos (GitHub, GitLab, etc.)
- from_hf / to_hf: Convert between ZDS and HuggingFace Dataset formats
- ZDSStore: Low-level key-value store interface (pure Python or native)
- NativeStore: High-performance Rust-backed store (when available)
- ZDataset: Map-style dataset (random access, __getitem__, __len__)
- ZIterableDataset: Streaming dataset with shuffle buffer
- read_zds / to_zds: DataFrame integration (requires pandas)
- query_zds / register_zds: DuckDB integration (requires duckdb)

Quick Start:
    from zippy import load_remote, ZDataset
    
    # Load from GitHub
    dataset = load_remote("zippydata/example-datasets")
    
    # Load from local path
    dataset = ZDataset.from_zds("./my_dataset", collection="train")
    
    # Convert to/from HuggingFace
    from zippy import from_hf, to_hf
    zds = from_hf(hf_dataset, "./output")
    hf = to_hf(zds)
    
    # Iterate
    for doc in dataset:
        print(doc)
"""

__version__ = "0.1.1"
__author__ = "Omar Kamali"

# Try to import native bindings
_HAS_NATIVE = False
try:
    from ._zippy_data import NativeStore, version as native_version
    _HAS_NATIVE = True
except ImportError:
    NativeStore = None
    native_version = None

from .store import ZDSStore
from .fast_store import FastZDSStore
from .dataset import ZDataset
from .iterable_dataset import ZIterableDataset
from .pandas_compat import read_zds, to_zds
from .hub import load_remote, dataset_info, clear_cache, from_hf, to_hf, to_hf_dict

# Re-export common functions
from .utils import (
    compute_schema_id,
    validate_doc_id,
    list_collections,
)

# DuckDB integration (lazy import)
def query_zds(*args, **kwargs):
    """Query ZDS with SQL. See duckdb_compat.query_zds for details."""
    from .duckdb_compat import query_zds as _query_zds
    return _query_zds(*args, **kwargs)

def register_zds(*args, **kwargs):
    """Register ZDS collection in DuckDB. See duckdb_compat.register_zds for details."""
    from .duckdb_compat import register_zds as _register_zds
    return _register_zds(*args, **kwargs)

__all__ = [
    # Main API
    "load_remote",
    "dataset_info",
    "clear_cache",
    # HuggingFace Integration
    "from_hf",
    "to_hf",
    "to_hf_dict",
    # Stores
    "ZDSStore",
    "FastZDSStore",
    # Datasets
    "ZDataset", 
    "ZIterableDataset",
    # Pandas integration
    "read_zds",
    "to_zds",
    # Utilities
    "compute_schema_id",
    "validate_doc_id",
    "list_collections",
    # DuckDB
    "query_zds",
    "register_zds",
    # Metadata
    "__version__",
]

# Try to import native core if available
try:
    from . import _core
    _HAS_NATIVE = True
except ImportError:
    _HAS_NATIVE = False


def get_backend() -> str:
    """Return the active backend ('native' or 'pure_python')."""
    return "native" if _HAS_NATIVE else "pure_python"
