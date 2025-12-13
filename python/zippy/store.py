"""ZDSStore - Low-level key-value store interface."""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from . import json_backend

from .utils import (
    ensure_collection_exists,
    validate_doc_id,
    compute_schema_id,
    docs_dir,
    doc_file,
    order_file,
    doc_index_file,
    schema_registry_file,
    manifest_file,
    iter_doc_ids,
    VERSION,
)


class ZDSStore:
    """Low-level ZDS store interface.
    
    Provides key-value operations on a ZDS collection with crash-safe writes.
    
    Example:
        >>> store = ZDSStore.open("./my_dataset", collection="train")
        >>> store.put("doc1", {"text": "hello", "label": 1})
        >>> store.get("doc1")
        {"text": "hello", "label": 1}
        >>> len(store)
        1
    """
    
    def __init__(
        self,
        root: Path,
        collection: str,
        strict: bool = False,
        _schema_id: Optional[str] = None,
        sync_writes: bool = False,
    ):
        """Initialize store (use ZDSStore.open() instead).
        
        Args:
            root: Store root path.
            collection: Collection name.
            strict: Enable strict schema mode.
            _schema_id: Required schema ID in strict mode (internal).
            sync_writes: If True, fsync after each write (slower but crash-safe).
        """
        self.root = Path(root)
        self.collection = collection
        self.strict = strict
        self._schema_id = _schema_id
        self._sync_writes = sync_writes
        self._doc_cache: Dict[str, Dict[str, Any]] = {}
        self._order: Optional[List[str]] = None
        self._bulk_mode = False
        self._pending_ids: List[str] = []
    
    @classmethod
    def open(
        cls,
        root: Union[str, Path],
        collection: str = "default",
        strict: bool = False,
        create: bool = True,
        sync_writes: bool = False,
    ) -> "ZDSStore":
        """Open or create a ZDS store.
        
        Args:
            root: Store root path.
            collection: Collection name.
            strict: Enable strict schema mode.
            create: Create store if it doesn't exist.
            sync_writes: If True, fsync after each write (slower but crash-safe).
            
        Returns:
            ZDSStore instance.
            
        Raises:
            FileNotFoundError: If store doesn't exist and create=False.
        """
        root_path = Path(root)
        
        if not root_path.exists():
            if create:
                ensure_collection_exists(root_path, collection)
            else:
                raise FileNotFoundError(f"Store not found: {root_path}")
        else:
            ensure_collection_exists(root_path, collection)
        
        # Load existing manifest if present
        manifest_path = manifest_file(root_path, collection)
        schema_id = None
        
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                strict = manifest.get("strict", strict)
                schema_id = manifest.get("schema_id")
        else:
            # Create initial manifest
            manifest = {
                "version": VERSION,
                "collection": collection,
                "strict": strict,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "doc_count": 0,
                "schema_count": 0,
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        
        return cls(root_path, collection, strict, schema_id, sync_writes)
    
    def put(self, doc_id: str, doc: Dict[str, Any]) -> None:
        """Write a document.
        
        Args:
            doc_id: Document ID.
            doc: Document data.
            
        Raises:
            ValueError: If doc_id is invalid.
            ValueError: If strict mode is enabled and schema doesn't match.
        """
        validate_doc_id(doc_id)
        
        # Schema validation in strict mode
        if self.strict:
            schema_id = compute_schema_id(doc)
            if self._schema_id is None:
                self._schema_id = schema_id
            elif schema_id != self._schema_id:
                raise ValueError(
                    f"Schema mismatch in strict mode: expected {self._schema_id[:16]}..., "
                    f"got {schema_id[:16]}..."
                )
        
        # Write document
        docs = docs_dir(self.root, self.collection)
        docs.mkdir(parents=True, exist_ok=True)
        
        final_path = doc_file(self.root, self.collection, doc_id)
        
        # Use compact JSON for performance (no indent)
        content = json_backend.dumps_compact(doc)
        
        if self._sync_writes:
            # Crash-safe write with temp file and fsync
            tmp_path = docs / f".{doc_id}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            tmp_path.rename(final_path)
        else:
            # Fast write (no fsync, no temp file)
            with open(final_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        # Update cache and order
        self._doc_cache[doc_id] = doc
        if self._bulk_mode:
            self._pending_ids.append(doc_id)
        else:
            self._invalidate_order()
    
    def get(self, doc_id: str) -> Dict[str, Any]:
        """Get a document by ID.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            Document data.
            
        Raises:
            KeyError: If document not found.
        """
        if doc_id in self._doc_cache:
            return self._doc_cache[doc_id]
        
        path = doc_file(self.root, self.collection, doc_id)
        if not path.exists():
            raise KeyError(f"Document not found: {doc_id}")
        
        with open(path, "rb") as f:
            doc = json_backend.loads(f.read())
        
        self._doc_cache[doc_id] = doc
        return doc
    
    def delete(self, doc_id: str) -> None:
        """Delete a document.
        
        Args:
            doc_id: Document ID.
            
        Raises:
            KeyError: If document not found.
        """
        path = doc_file(self.root, self.collection, doc_id)
        if not path.exists():
            raise KeyError(f"Document not found: {doc_id}")
        
        path.unlink()
        self._doc_cache.pop(doc_id, None)
        self._invalidate_order()
    
    def exists(self, doc_id: str) -> bool:
        """Check if document exists.
        
        Args:
            doc_id: Document ID.
            
        Returns:
            True if document exists.
        """
        return doc_file(self.root, self.collection, doc_id).exists()
    
    def scan(
        self,
        fields: Optional[List[str]] = None,
        predicate: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate over all documents.
        
        Args:
            fields: Optional list of fields to project.
            predicate: Optional simple equality predicate.
            
        Yields:
            Documents matching the predicate.
        """
        for doc_id in self.list_doc_ids():
            try:
                doc = self.get(doc_id)
            except (KeyError, json.JSONDecodeError):
                continue
            
            # Apply predicate
            if predicate:
                if not all(doc.get(k) == v for k, v in predicate.items()):
                    continue
            
            # Apply projection
            if fields:
                doc = {k: doc.get(k) for k in fields if k in doc}
            
            yield doc
    
    def list_doc_ids(self) -> List[str]:
        """Get all document IDs in stable order.
        
        Returns:
            List of document IDs.
        """
        if self._order is None:
            self._order = list(iter_doc_ids(self.root, self.collection))
            
            # If order.ids is empty/missing, rebuild from disk
            if not self._order:
                docs = docs_dir(self.root, self.collection)
                if docs.exists():
                    self._order = sorted(p.stem for p in docs.glob("*.json"))
        
        return self._order
    
    def count(self) -> int:
        """Get document count.
        
        Returns:
            Number of documents.
        """
        return len(self.list_doc_ids())
    
    def _invalidate_order(self) -> None:
        """Invalidate cached order (call after put/delete)."""
        self._order = None
    
    def bulk_write(self) -> "BulkWriteContext":
        """Context manager for bulk write operations.
        
        Defers order invalidation until all writes complete.
        
        Example:
            >>> with store.bulk_write():
            ...     for i in range(10000):
            ...         store.put(f"doc_{i}", {"value": i})
        """
        return BulkWriteContext(self)
    
    def preload(self) -> None:
        """Preload all documents into cache for fast access."""
        docs = docs_dir(self.root, self.collection)
        if not docs.exists():
            return
        
        for path in docs.glob("*.json"):
            doc_id = path.stem
            if doc_id not in self._doc_cache:
                try:
                    with open(path, "rb") as f:
                        self._doc_cache[doc_id] = json_backend.loads(f.read())
                except (IOError, ValueError):
                    pass
    
    def scan_fast(self) -> Iterator[Dict[str, Any]]:
        """Fast scan using bulk file reading.
        
        More efficient than scan() for full collection reads.
        """
        docs = docs_dir(self.root, self.collection)
        if not docs.exists():
            return
        
        for path in docs.glob("*.json"):
            try:
                with open(path, "rb") as f:
                    yield json_backend.loads(f.read())
            except (IOError, ValueError):
                continue
    
    def to_dataset(self) -> "ZDataset":
        """Convert to map-style dataset.
        
        Returns:
            ZDataset instance.
        """
        from .dataset import ZDataset
        return ZDataset(self)
    
    def to_iterable_dataset(self) -> "ZIterableDataset":
        """Convert to iterable dataset.
        
        Returns:
            ZIterableDataset instance.
        """
        from .iterable_dataset import ZIterableDataset
        return ZIterableDataset(self)
    
    def __contains__(self, doc_id: str) -> bool:
        """Check if document exists."""
        return self.exists(doc_id)
    
    def __getitem__(self, doc_id: str) -> Dict[str, Any]:
        """Get document by ID."""
        return self.get(doc_id)
    
    def __setitem__(self, doc_id: str, doc: Dict[str, Any]) -> None:
        """Set document by ID."""
        self.put(doc_id, doc)
    
    def __delitem__(self, doc_id: str) -> None:
        """Delete document by ID."""
        self.delete(doc_id)
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over documents."""
        return self.scan()
    
    def __len__(self) -> int:
        """Get document count."""
        return self.count()
    
    def __repr__(self) -> str:
        return f"ZDSStore(root={self.root}, collection={self.collection!r}, count={self.count()})"


class BulkWriteContext:
    """Context manager for bulk write operations."""
    
    def __init__(self, store: ZDSStore):
        self.store = store
    
    def __enter__(self) -> ZDSStore:
        self.store._bulk_mode = True
        self.store._pending_ids = []
        return self.store
    
    def __exit__(self, *args) -> None:
        self.store._bulk_mode = False
        if self.store._pending_ids:
            self.store._invalidate_order()
        self.store._pending_ids = []
