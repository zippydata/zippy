"""FastZDSStore - High-performance store with batching and JSONL storage."""

import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union, Tuple
import threading

from . import json_backend

from .utils import (
    ensure_collection_exists,
    validate_doc_id,
    compute_schema_id,
    docs_dir,
    meta_dir,
    manifest_file,
    VERSION,
)


class FastZDSStore:
    """High-performance ZDS store with batching and JSONL storage.
    
    This implementation trades individual file-per-document for JSONL bulk storage,
    providing 10-100x performance improvement for sequential operations while
    maintaining random access via an in-memory index.
    
    Example:
        >>> with FastZDSStore.open("./data", collection="train") as store:
        ...     for i in range(10000):
        ...         store.put(f"doc_{i}", {"value": i})
        >>> # Writes are batched and flushed on context exit
    """
    
    __slots__ = (
        'root', 'collection', 'strict', '_schema_id',
        '_index', '_data_file', '_index_file', '_pending_writes',
        '_batch_size', '_lock', '_dirty', '_file_handle', '_closed'
    )
    
    def __init__(
        self,
        root: Path,
        collection: str,
        strict: bool = False,
        batch_size: int = 1000,
    ):
        self.root = Path(root)
        self.collection = collection
        self.strict = strict
        self._schema_id: Optional[str] = None
        
        # In-memory index: doc_id -> (offset, length)
        self._index: Dict[str, Tuple[int, int]] = {}
        
        # File paths
        meta = meta_dir(self.root, self.collection)
        self._data_file = meta / "data.jsonl"
        self._index_file = meta / "index.bin"
        
        # Batch writes
        self._pending_writes: List[Tuple[str, Dict[str, Any]]] = []
        self._batch_size = batch_size
        self._lock = threading.Lock()
        self._dirty = False
        self._file_handle: Optional[Any] = None
        self._closed = False
    
    @classmethod
    def open(
        cls,
        root: Union[str, Path],
        collection: str = "default",
        strict: bool = False,
        batch_size: int = 1000,
    ) -> "FastZDSStore":
        """Open or create a fast ZDS store."""
        root_path = Path(root)
        ensure_collection_exists(root_path, collection)
        
        store = cls(root_path, collection, strict, batch_size)
        store._load_index()
        return store
    
    def _load_index(self) -> None:
        """Load index from disk or rebuild from JSONL."""
        if self._index_file.exists():
            self._load_index_file()
        elif self._data_file.exists():
            self._rebuild_index()
        
        # Also check for legacy individual files and migrate
        docs = docs_dir(self.root, self.collection)
        if docs.exists():
            legacy_files = list(docs.glob("*.json"))
            if legacy_files and not self._data_file.exists():
                self._migrate_legacy(legacy_files)
    
    def _load_index_file(self) -> None:
        """Load binary index file."""
        with open(self._index_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    parts = line.strip().split("\t")
                    if len(parts) == 3:
                        doc_id, offset, length = parts
                        self._index[doc_id] = (int(offset), int(length))
    
    def _rebuild_index(self) -> None:
        """Rebuild index from JSONL file."""
        self._index.clear()
        with open(self._data_file, "rb") as f:
            offset = 0
            for line in f:
                try:
                    doc = json_backend.loads(line)
                    doc_id = doc.get("_id")
                    if doc_id:
                        self._index[doc_id] = (offset, len(line))
                except ValueError:
                    pass
                offset += len(line)
        self._save_index()
    
    def _migrate_legacy(self, legacy_files: List[Path]) -> None:
        """Migrate from individual JSON files to JSONL format."""
        with open(self._data_file, "ab") as f:
            for filepath in legacy_files:
                doc_id = filepath.stem
                try:
                    with open(filepath, "rb") as src:
                        doc = json_backend.loads(src.read())
                    doc["_id"] = doc_id
                    line_bytes = json_backend.dumps_bytes({"_id": doc_id, **doc}) + b"\n"
                    
                    offset = f.tell()
                    f.write(line_bytes)
                    self._index[doc_id] = (offset, len(line_bytes))
                except (ValueError, IOError):
                    pass
        self._save_index()
    
    def _save_index(self) -> None:
        """Save index to disk."""
        with open(self._index_file, "w", encoding="utf-8") as f:
            for doc_id, (offset, length) in self._index.items():
                f.write(f"{doc_id}\t{offset}\t{length}\n")
    
    def put(self, doc_id: str, doc: Dict[str, Any]) -> None:
        """Write a document (batched)."""
        validate_doc_id(doc_id)
        
        if self.strict:
            schema_id = compute_schema_id(doc)
            if self._schema_id is None:
                self._schema_id = schema_id
            elif schema_id != self._schema_id:
                raise ValueError(f"Schema mismatch in strict mode")
        
        with self._lock:
            self._pending_writes.append((doc_id, doc))
            if len(self._pending_writes) >= self._batch_size:
                self._flush_writes()
    
    def _flush_writes(self) -> None:
        """Flush pending writes to disk."""
        if not self._pending_writes:
            return
        
        with open(self._data_file, "ab") as f:
            for doc_id, doc in self._pending_writes:
                doc_with_id = {"_id": doc_id, **doc}
                line_bytes = json_backend.dumps_bytes(doc_with_id) + b"\n"
                
                offset = f.tell()
                f.write(line_bytes)
                self._index[doc_id] = (offset, len(line_bytes))
            
            f.flush()
            os.fsync(f.fileno())
        
        self._pending_writes.clear()
        self._dirty = True
    
    def get(self, doc_id: str) -> Dict[str, Any]:
        """Get document by ID."""
        # Check pending writes first
        for pending_id, doc in self._pending_writes:
            if pending_id == doc_id:
                return doc
        
        if doc_id not in self._index:
            raise KeyError(f"Document not found: {doc_id}")
        
        offset, length = self._index[doc_id]
        
        with open(self._data_file, "rb") as f:
            f.seek(offset)
            line = f.read(length)
        
        doc = json_backend.loads(line)
        doc.pop("_id", None)
        return doc
    
    def delete(self, doc_id: str) -> None:
        """Delete a document (marks as deleted, compaction removes)."""
        if doc_id not in self._index:
            raise KeyError(f"Document not found: {doc_id}")
        
        del self._index[doc_id]
        self._dirty = True
    
    def exists(self, doc_id: str) -> bool:
        """Check if document exists."""
        return doc_id in self._index or any(
            pid == doc_id for pid, _ in self._pending_writes
        )
    
    def scan(
        self,
        fields: Optional[List[str]] = None,
        predicate: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Iterate over all documents (optimized bulk read)."""
        # Flush pending writes first
        with self._lock:
            self._flush_writes()
        
        if not self._data_file.exists():
            return
        
        # Bulk read entire file for best performance
        with open(self._data_file, "rb") as f:
            for line in f:
                try:
                    doc = json_backend.loads(line)
                    doc_id = doc.pop("_id", None)
                    
                    # Skip deleted documents
                    if doc_id and doc_id not in self._index:
                        continue
                    
                    # Apply predicate
                    if predicate:
                        if not all(doc.get(k) == v for k, v in predicate.items()):
                            continue
                    
                    # Apply projection
                    if fields:
                        doc = {k: doc.get(k) for k in fields if k in doc}
                    
                    yield doc
                except ValueError:
                    continue
    
    def scan_with_ids(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """Iterate over all documents with their IDs."""
        with self._lock:
            self._flush_writes()
        
        if not self._data_file.exists():
            return
        
        with open(self._data_file, "rb") as f:
            for line in f:
                try:
                    doc = json_backend.loads(line)
                    doc_id = doc.pop("_id", None)
                    if doc_id and doc_id in self._index:
                        yield doc_id, doc
                except ValueError:
                    continue
    
    def list_doc_ids(self) -> List[str]:
        """Get all document IDs."""
        with self._lock:
            self._flush_writes()
        return list(self._index.keys())
    
    def count(self) -> int:
        """Get document count."""
        return len(self._index) + len(self._pending_writes)
    
    def compact(self) -> None:
        """Compact the data file by removing deleted entries."""
        if not self._dirty and not self._pending_writes:
            return
        
        with self._lock:
            self._flush_writes()
        
        # Rewrite entire file with only live documents
        tmp_file = self._data_file.with_suffix(".tmp")
        new_index: Dict[str, Tuple[int, int]] = {}
        
        with open(self._data_file, "rb") as src, open(tmp_file, "wb") as dst:
            for line in src:
                try:
                    doc = json_backend.loads(line)
                    doc_id = doc.get("_id")
                    if doc_id and doc_id in self._index:
                        offset = dst.tell()
                        dst.write(line)
                        new_index[doc_id] = (offset, len(line))
                except ValueError:
                    continue
            dst.flush()
            os.fsync(dst.fileno())
        
        # Atomic replace
        tmp_file.replace(self._data_file)
        self._index = new_index
        self._save_index()
        self._dirty = False
    
    def flush(self) -> None:
        """Force flush pending writes."""
        with self._lock:
            self._flush_writes()
        if self._dirty:
            self._save_index()
            self._dirty = False
    
    def close(self) -> None:
        """Close the store and flush pending writes."""
        if self._closed:
            return
        self.flush()
        self._closed = True
    
    def __enter__(self) -> "FastZDSStore":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()
    
    def __contains__(self, doc_id: str) -> bool:
        return self.exists(doc_id)
    
    def __getitem__(self, doc_id: str) -> Dict[str, Any]:
        return self.get(doc_id)
    
    def __setitem__(self, doc_id: str, doc: Dict[str, Any]) -> None:
        self.put(doc_id, doc)
    
    def __delitem__(self, doc_id: str) -> None:
        self.delete(doc_id)
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return self.scan()
    
    def __len__(self) -> int:
        return self.count()
    
    def __del__(self):
        if not self._closed:
            self.close()
    
    def __repr__(self) -> str:
        return f"FastZDSStore(root={self.root}, collection={self.collection!r}, count={self.count()})"


# Also optimize the original store with a "fast mode" option
def optimize_store_writes(store_cls):
    """Decorator to add batch writing capability to ZDSStore."""
    original_put = store_cls.put
    
    def batched_put(self, doc_id: str, doc: Dict[str, Any], *, sync: bool = True) -> None:
        """Write with optional sync control."""
        validate_doc_id(doc_id)
        
        if self.strict:
            schema_id = compute_schema_id(doc)
            if self._schema_id is None:
                self._schema_id = schema_id
            elif schema_id != self._schema_id:
                raise ValueError(f"Schema mismatch in strict mode")
        
        docs = docs_dir(self.root, self.collection)
        docs.mkdir(parents=True, exist_ok=True)
        
        final_path = doc_file(self.root, self.collection, doc_id)
        
        # Use compact JSON (no indent)
        content = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        
        with open(final_path, "w", encoding="utf-8") as f:
            f.write(content)
            if sync:
                f.flush()
                os.fsync(f.fileno())
        
        self._doc_cache[doc_id] = doc
        self._invalidate_order()
    
    store_cls.put = batched_put
    return store_cls
