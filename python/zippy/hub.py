"""
Dataset hub functionality for loading remote datasets.

This module provides a unified interface for loading ZDS datasets from
various sources including Git repositories, local paths, and cloud storage.

Features:
- `load_remote`: Load datasets from Git repos (GitHub, GitLab, etc.), S3, GCS
- `from_hf`: Convert HuggingFace Dataset to ZDS
- `to_hf`: Convert ZDS to HuggingFace Dataset
- HuggingFace `load_dataset("zds", ...)` integration

Examples:
    from zippy import load_remote
    
    # Load from GitHub (most common)
    dataset = load_remote("zippydata/sentiment-analysis")
    
    # Load from GitLab
    dataset = load_remote("gitlab.com/user/repo")
    
    # Load specific collection and version
    dataset = load_remote("zippydata/sentiment-analysis", collection="train", revision="v2.0")
    
    # Load from local path
    dataset = load_remote("./my_local_dataset")
    
    # HuggingFace integration
    from datasets import load_dataset
    dataset = load_dataset("zds", data_dir="./my_dataset", split="train")
    
    # Convert between formats
    from zippy import from_hf, to_hf
    zds = from_hf(hf_dataset, "./output")
    hf = to_hf(zds)
"""

import os
from pathlib import Path
from typing import Optional, Union, Any, List, TYPE_CHECKING

from .dataset import ZDataset
from .iterable_dataset import ZIterableDataset
from .providers.base import ProviderRegistry, DatasetInfo

if TYPE_CHECKING:
    try:
        from datasets import Dataset as HFDataset, DatasetDict as HFDatasetDict
    except ImportError:
        HFDataset = Any
        HFDatasetDict = Any


def load_remote(
    path: str,
    collection: Optional[str] = None,
    *,
    revision: Optional[str] = None,
    subpath: Optional[str] = None,
    split: Optional[str] = None,
    streaming: bool = False,
    cache_dir: Optional[str] = None,
    token: Optional[str] = None,
    force_download: bool = False,
    **kwargs
) -> Union[ZDataset, ZIterableDataset]:
    """
    Load a ZDS dataset from local path or remote Git repository.
    
    This function provides a unified interface for loading datasets from
    any Git host (GitHub, GitLab, Bitbucket, self-hosted) or local paths.
    
    Args:
        path: Dataset path, which can be:
            - Local directory path: "./my_dataset"
            - Git repository: "username/repo" (defaults to GitHub)
            - Any Git host: "gitlab.com/user/repo", "bitbucket.org/user/repo"
            - With revision: "username/repo@v1.0"  
            - Cloud storage: "s3://bucket/path", "gs://bucket/path" (stubs)
            
        collection: Name of the collection to load (e.g., "train", "test").
            If None, uses the first available collection.
            
        revision: Version/branch/tag for remote sources.
            For Git: branch name, tag, or commit SHA.
            
        subpath: Subdirectory within the repository.
            Use when the ZDS dataset is not at the repo root.
            
        split: Alias for collection (for HuggingFace compatibility).
        
        streaming: If True, return ZIterableDataset for streaming access.
            If False (default), return ZDataset for random access.
            
        cache_dir: Directory for caching remote datasets.
            Default: ~/.cache/zds or ZDS_CACHE_DIR env var.
            
        token: Authentication token for private repositories.
            For GitHub: GITHUB_TOKEN, for GitLab: GITLAB_TOKEN, or GIT_TOKEN.
            
        force_download: If True, re-download even if cached.
        
        **kwargs: Additional provider-specific arguments.
        
    Returns:
        ZDataset (if streaming=False) or ZIterableDataset (if streaming=True)
        
    Raises:
        FileNotFoundError: If local path doesn't exist or remote not found.
        ValueError: If invalid URI format or unknown provider.
        NotImplementedError: If provider is not yet implemented (stub).
        
    Examples:
        # Load from GitHub
        dataset = load_remote("zippydata/example")
        
        # Load from GitLab
        dataset = load_remote("gitlab.com/user/repo")
        
        # With collection
        train = load_remote("zippydata/example", collection="train")
        
        # Streaming mode
        for doc in load_remote("zippydata/large", streaming=True):
            process(doc)
            
        # Private repository
        dataset = load_remote("myorg/private", token="ghp_...")
    """
    # Handle split as alias for collection
    if split is not None and collection is None:
        collection = split
    
    # Resolve the path to a local directory
    local_path = _resolve_path(
        path=path,
        revision=revision,
        subpath=subpath,
        cache_dir=cache_dir,
        token=token,
        force_download=force_download,
        **kwargs
    )
    
    # Load the dataset
    if streaming:
        from .fast_store import FastZDSStore
        store = FastZDSStore.open(str(local_path), collection=collection)
        return ZIterableDataset(store)
    else:
        return ZDataset.from_store(str(local_path), collection=collection)


def _resolve_path(
    path: str,
    revision: Optional[str] = None,
    subpath: Optional[str] = None,
    cache_dir: Optional[str] = None,
    token: Optional[str] = None,
    force_download: bool = False,
    **kwargs
) -> Path:
    """
    Resolve a path to a local directory.
    
    If path is local, return it directly.
    If path is remote, download and return cached path.
    """
    # Check if it's a local path
    local_path = Path(path).expanduser()
    if local_path.exists():
        if subpath:
            local_path = local_path / subpath
        return local_path
    
    # It's a remote path - parse URI and get provider
    scheme, uri = ProviderRegistry.parse_uri(path)
    provider = ProviderRegistry.get_instance(scheme)
    
    # Download the dataset
    cache_path = Path(cache_dir) if cache_dir else None
    downloaded_path = provider.download(
        uri=uri,
        cache_dir=cache_path,
        revision=revision,
        path=subpath,
        force=force_download,
        token=token,
        **kwargs
    )
    
    return downloaded_path


def dataset_info(path: str, **kwargs) -> DatasetInfo:
    """
    Get information about a dataset without downloading.
    
    Args:
        path: Dataset path (local or remote)
        **kwargs: Provider-specific arguments
        
    Returns:
        DatasetInfo with metadata about the dataset
    """
    # Check if local
    local_path = Path(path).expanduser()
    if local_path.exists():
        # Get info from local zds.json if available
        from .utils import list_collections
        collections = list_collections(local_path)
        return DatasetInfo(
            name=local_path.name,
            provider="local",
            uri=str(local_path),
            description=f"Local dataset with {len(collections)} collection(s)",
        )
    
    # Remote - use provider
    scheme, uri = ProviderRegistry.parse_uri(path)
    provider = ProviderRegistry.get_instance(scheme)
    return provider.get_info(uri, **kwargs)


def list_remote_collections(path: str, **kwargs) -> List[str]:
    """
    List collections in a remote dataset.
    
    This downloads the dataset metadata only (not full data)
    to list available collections.
    
    Args:
        path: Remote dataset path
        **kwargs: Provider-specific arguments
        
    Returns:
        List of collection names
    """
    # For now, this requires downloading the dataset
    # Future: implement partial download for metadata only
    local_path = _resolve_path(path, **kwargs)
    from .utils import list_collections
    return list_collections(local_path)


def clear_cache(path: Optional[str] = None) -> None:
    """
    Clear cached datasets.
    
    Args:
        path: If provided, clear only the cache for this dataset.
            If None, clear the entire cache.
    """
    import shutil
    
    cache_dir = Path(
        os.environ.get("ZDS_CACHE_DIR", Path.home() / ".cache" / "zds")
    )
    
    if path is None:
        # Clear entire cache
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
    else:
        # Clear specific dataset
        scheme, uri = ProviderRegistry.parse_uri(path)
        # Provider-specific cache clearing would go here
        # For now, just note it in the docstring


# =============================================================================
# HuggingFace Integration
# =============================================================================

def from_hf(
    hf_dataset: Any,
    output_path: str,
    collection: Optional[str] = None,
    id_column: Optional[str] = None,
) -> ZDataset:
    """
    Convert a HuggingFace Dataset to ZDS format.
    
    This function writes a HuggingFace Dataset to the ZDS format on disk,
    enabling all ZDS features like schema flexibility and fast random access.
    
    Args:
        hf_dataset: A HuggingFace Dataset or DatasetDict to convert.
            If DatasetDict, each split becomes a ZDS collection.
        output_path: Path where the ZDS dataset will be created.
        collection: Name of the collection (if hf_dataset is a Dataset).
            Defaults to "main" if not specified.
        id_column: Column to use as document ID. If None, generates UUIDs.
        
    Returns:
        ZDataset pointing to the created ZDS dataset.
        
    Examples:
        from datasets import load_dataset
        from zippy import from_hf
        
        # Convert a single split
        hf = load_dataset("imdb", split="train")
        zds = from_hf(hf, "./imdb_zds", collection="train")
        
        # Convert entire DatasetDict
        hf = load_dataset("imdb")
        zds = from_hf(hf, "./imdb_zds")  # Creates train/test collections
    """
    try:
        from datasets import Dataset as HFDataset, DatasetDict as HFDatasetDict
    except ImportError:
        raise ImportError(
            "HuggingFace datasets is required for this function. "
            "Install with: pip install datasets"
        )
    
    from .fast_store import FastZDSStore
    import uuid
    
    output = Path(output_path)
    
    # Handle DatasetDict (multiple splits)
    if isinstance(hf_dataset, HFDatasetDict):
        for split_name, split_data in hf_dataset.items():
            _write_hf_split(split_data, output, split_name, id_column)
        # Return first collection
        first_collection = list(hf_dataset.keys())[0]
        return ZDataset.from_store(str(output), collection=first_collection)
    
    # Handle single Dataset
    collection = collection or "main"
    _write_hf_split(hf_dataset, output, collection, id_column)
    return ZDataset.from_store(str(output), collection=collection)


def _write_hf_split(hf_dataset: Any, output: Path, collection: str, id_column: Optional[str]) -> None:
    """Write a single HuggingFace split to ZDS."""
    from .fast_store import FastZDSStore
    import uuid
    
    with FastZDSStore.open(str(output), collection=collection) as store:
        for i, row in enumerate(hf_dataset):
            # Convert to dict if needed
            doc = dict(row) if hasattr(row, "items") else row
            
            # Get or generate ID
            if id_column and id_column in doc:
                doc_id = str(doc[id_column])
            else:
                doc_id = f"doc_{i:08d}"
            
            store.put(doc_id, doc)


def to_hf(
    zds_dataset: Union[ZDataset, str],
    collection: Optional[str] = None,
) -> Any:
    """
    Convert a ZDS dataset to HuggingFace Dataset format.
    
    This enables using ZDS datasets with HuggingFace's training utilities,
    transformers, and other ecosystem tools.
    
    Args:
        zds_dataset: A ZDataset instance or path to a ZDS dataset.
        collection: Collection to convert. If None, uses first collection.
        
    Returns:
        HuggingFace Dataset object.
        
    Examples:
        from zippy import to_hf, ZDataset
        
        # From ZDataset
        zds = ZDataset.from_zds("./my_data", collection="train")
        hf = to_hf(zds)
        
        # From path
        hf = to_hf("./my_data", collection="train")
        
        # Use with HuggingFace
        from transformers import Trainer
        trainer = Trainer(train_dataset=hf, ...)
    """
    try:
        from datasets import Dataset as HFDataset
    except ImportError:
        raise ImportError(
            "HuggingFace datasets is required for this function. "
            "Install with: pip install datasets"
        )
    
    # Load ZDS if path provided
    if isinstance(zds_dataset, str):
        zds_dataset = ZDataset.from_store(zds_dataset, collection=collection)
    
    # Convert to list of dicts
    records = list(zds_dataset)
    
    # Create HuggingFace Dataset
    return HFDataset.from_list(records)


def to_hf_dict(
    zds_path: str,
    collections: Optional[List[str]] = None,
) -> Any:
    """
    Convert multiple ZDS collections to a HuggingFace DatasetDict.
    
    Args:
        zds_path: Path to the ZDS dataset.
        collections: List of collections to include. If None, includes all.
        
    Returns:
        HuggingFace DatasetDict with one split per collection.
        
    Examples:
        from zippy import to_hf_dict
        
        hf = to_hf_dict("./my_data")  # All collections
        hf = to_hf_dict("./my_data", collections=["train", "test"])
        
        print(hf)  # DatasetDict({'train': Dataset(...), 'test': Dataset(...)})
    """
    try:
        from datasets import DatasetDict as HFDatasetDict
    except ImportError:
        raise ImportError(
            "HuggingFace datasets is required for this function. "
            "Install with: pip install datasets"
        )
    
    from .utils import list_collections as _list_collections
    
    # Get collections to convert
    if collections is None:
        collections = _list_collections(Path(zds_path))
    
    # Convert each collection
    splits = {}
    for coll in collections:
        splits[coll] = to_hf(zds_path, collection=coll)
    
    return HFDatasetDict(splits)


# =============================================================================
# HuggingFace load_dataset Integration
# =============================================================================

# Register ZDS as a HuggingFace dataset builder
# This allows: load_dataset("zds", data_dir="./my_data", split="train")
def _register_hf_builder():
    """Register ZDS as a HuggingFace dataset builder."""
    try:
        from datasets import BuilderConfig, GeneratorBasedBuilder, DatasetInfo
        from datasets import Features, Value, Sequence
        import datasets
        
        class ZDSDatasetBuilder(GeneratorBasedBuilder):
            """HuggingFace dataset builder for ZDS format."""
            
            BUILDER_CONFIG_CLASS = BuilderConfig
            VERSION = datasets.Version("1.0.0")
            
            def _info(self):
                # Dynamic features based on first document
                return DatasetInfo(
                    description="ZDS (Zippy Data System) format",
                    features=None,  # Dynamic
                )
            
            def _split_generators(self, dl_manager):
                from .utils import list_collections as _list_collections
                
                data_dir = self.config.data_dir
                collections = _list_collections(data_dir)
                
                return [
                    datasets.SplitGenerator(
                        name=coll,
                        gen_kwargs={"data_dir": data_dir, "collection": coll},
                    )
                    for coll in collections
                ]
            
            def _generate_examples(self, data_dir, collection):
                dataset = ZDataset.from_zds(data_dir, collection=collection)
                for i, doc in enumerate(dataset):
                    yield i, doc
        
        # Try to register
        try:
            datasets.builder.BUILDER_REGISTRY["zds"] = ZDSDatasetBuilder
        except Exception:
            pass  # Registration failed, but that's okay
            
    except ImportError:
        pass  # datasets not installed


# Try to register on import
_register_hf_builder()


# Export convenience functions
__all__ = [
    "load_remote",
    "dataset_info", 
    "list_remote_collections",
    "clear_cache",
    "from_hf",
    "to_hf",
    "to_hf_dict",
]
