"""ZDSRoot - Root-level store handle for managing multiple collections."""

from pathlib import Path
from typing import List, Literal, Optional, Union

# Try to import native bindings
_HAS_NATIVE = False
NativeRoot = None
try:
    from ._zippy_data import NativeRoot
    _HAS_NATIVE = True
except ImportError:
    pass

from .store import ZDSStore
from .fast_store import FastZDSStore
from .utils import ensure_collection_exists, list_collections


class ZDSRoot:
    """Root handle for a ZDS store directory.
    
    This class represents a ZDS root directory without binding to a specific collection.
    It allows opening multiple collections from the same root safely, avoiding corruption
    when writing to multiple collections simultaneously.
    
    Example:
        >>> root = ZDSRoot.open("./data")
        >>> train = root.collection("train")
        >>> test = root.collection("test")
        >>> train.put("doc1", {"split": "train"})
        >>> test.put("doc1", {"split": "test"})
        
    Use the `native=True` parameter to use the high-performance Rust backend:
        >>> root = ZDSRoot.open("./data", native=True)
        >>> train = root.collection("train")  # Returns native store handle
        
    Use `mode="r"` for read-only access (no locking):
        >>> root = ZDSRoot.open("./data", mode="r", native=True)
    """
    
    def __init__(
        self,
        root: Path,
        batch_size: int = 5000,
        native: bool = False,
        mode: str = "rw",
        _native_root: Optional["NativeRoot"] = None,
    ):
        """Initialize root (use ZDSRoot.open() instead).
        
        Args:
            root: Store root path.
            batch_size: Default batch size for collections.
            native: Use native Rust backend if available.
            mode: Open mode - "r" for read-only, "rw" for read-write.
            _native_root: Internal native root handle.
        """
        self.root = Path(root)
        self._batch_size = batch_size
        self._native = native and _HAS_NATIVE
        self._mode = mode
        self._native_root = _native_root
    
    @classmethod
    def open(
        cls,
        root: Union[str, Path],
        batch_size: int = 5000,
        native: bool = False,
        mode: Literal["r", "rw"] = "rw",
    ) -> "ZDSRoot":
        """Open or create a ZDS root directory.
        
        This initializes the root directory structure but does not open any collection.
        Use `collection()` to get a handle to a specific collection.
        
        Args:
            root: Store root path.
            batch_size: Default batch size for collections.
            native: Use native Rust backend if available.
            mode: Open mode - "r" for read-only, "rw" for read-write.
            
        Returns:
            ZDSRoot instance.
        """
        root_path = Path(root)
        
        # Initialize directory structure (only in rw mode)
        if mode == "rw":
            root_path.mkdir(parents=True, exist_ok=True)
            (root_path / "collections").mkdir(exist_ok=True)
            (root_path / "metadata").mkdir(exist_ok=True)
        
        native_root = None
        if native and _HAS_NATIVE:
            native_root = NativeRoot.open(str(root_path), batch_size, mode)
        
        return cls(root_path, batch_size, native, mode, native_root)
    
    @property
    def root_path(self) -> Path:
        """Get the root path."""
        return self.root
    
    @property
    def batch_size(self) -> int:
        """Get the default batch size."""
        return self._batch_size
    
    @property
    def mode(self) -> str:
        """Get the open mode ('r' or 'rw')."""
        if self._native_root is not None:
            return self._native_root.mode
        return self._mode
    
    @property
    def is_writable(self) -> bool:
        """Check if this root is writable."""
        if self._native_root is not None:
            return self._native_root.is_writable
        return self._mode == "rw"
    
    def collection(
        self,
        name: str,
        batch_size: Optional[int] = None,
        strict: bool = False,
    ):
        """Open a collection within this ZDS root.
        
        Creates the collection if it doesn't exist.
        
        Args:
            name: Collection name.
            batch_size: Override default batch size.
            strict: Enable strict schema mode (pure Python only).
            
        Returns:
            Store handle for the collection (NativeStore if native=True and available,
            otherwise ZDSStore).
        """
        bs = batch_size or self.batch_size
        
        if self._native_root is not None:
            # Use native backend - returns NativeStore
            return self._native_root.collection(name, bs)
        
        # Use FastZDSStore for better performance when native was requested but unavailable
        if self._native:
            return FastZDSStore.open(self.root, name, batch_size=bs)
        
        return ZDSStore.open(self.root, name, strict=strict)
    
    def list_collections(self) -> List[str]:
        """List all collections in this ZDS root.
        
        Returns:
            List of collection names.
        """
        if self._native_root is not None:
            return self._native_root.list_collections()
        return list_collections(self.root)
    
    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists.
        
        Args:
            name: Collection name.
            
        Returns:
            True if collection exists.
        """
        if self._native_root is not None:
            return self._native_root.collection_exists(name)
        collection_dir = self.root / "collections" / name
        return collection_dir.exists()
    
    def close(self) -> None:
        """Close the root and release any locks.
        
        This should be called when done with the root to release the write lock
        (if held) and allow other processes to access the store.
        """
        if self._native_root is not None:
            self._native_root.close()
    
    def __enter__(self) -> "ZDSRoot":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - closes the root."""
        self.close()
    
    def __repr__(self) -> str:
        collections = self.list_collections()
        backend = "native" if self._native else "pure_python"
        mode = self.mode
        return f"ZDSRoot(root={self.root}, mode={mode!r}, collections={collections}, backend={backend})"
