"""Utility functions for ZDS."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

# Layout constants (matching Rust core)
COLLECTIONS_DIR = "collections"
METADATA_DIR = "metadata"
DOCS_DIR = "docs"
META_DIR = "meta"
SCHEMA_REGISTRY_FILE = "schemas.jsonl"
DOC_INDEX_FILE = "doc_index.jsonl"
ORDER_FILE = "order.ids"
JOURNAL_FILE = "journal.log"
MANIFEST_FILE = "manifest.json"
VERSION = "0.1.0"


def collections_dir(root: Path) -> Path:
    """Get collections directory path."""
    return root / COLLECTIONS_DIR


def metadata_dir(root: Path) -> Path:
    """Get metadata directory path."""
    return root / METADATA_DIR


def collection_dir(root: Path, collection: str) -> Path:
    """Get collection directory path."""
    return collections_dir(root) / collection


def docs_dir(root: Path, collection: str) -> Path:
    """Get docs directory path for a collection."""
    return collection_dir(root, collection) / DOCS_DIR


def meta_dir(root: Path, collection: str) -> Path:
    """Get meta directory path for a collection."""
    return collection_dir(root, collection) / META_DIR


def doc_file(root: Path, collection: str, doc_id: str) -> Path:
    """Get path to a document file."""
    return docs_dir(root, collection) / f"{doc_id}.json"


def schema_registry_file(root: Path, collection: str) -> Path:
    """Get schema registry file path."""
    return meta_dir(root, collection) / SCHEMA_REGISTRY_FILE


def doc_index_file(root: Path, collection: str) -> Path:
    """Get document index file path."""
    return meta_dir(root, collection) / DOC_INDEX_FILE


def order_file(root: Path, collection: str) -> Path:
    """Get order file path."""
    return meta_dir(root, collection) / ORDER_FILE


def journal_file(root: Path, collection: str) -> Path:
    """Get journal file path."""
    return meta_dir(root, collection) / JOURNAL_FILE


def manifest_file(root: Path, collection: str) -> Path:
    """Get manifest file path."""
    return meta_dir(root, collection) / MANIFEST_FILE


def ensure_collection_exists(root: Path, collection: str) -> None:
    """Ensure collection directories exist."""
    docs = docs_dir(root, collection)
    meta = meta_dir(root, collection)
    
    docs.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)


def validate_doc_id(doc_id: str) -> bool:
    """Validate a document ID.
    
    Args:
        doc_id: Document ID to validate.
        
    Returns:
        True if valid.
        
    Raises:
        ValueError: If doc_id is invalid.
    """
    if not doc_id:
        raise ValueError("Document ID cannot be empty")
    
    # Only allow alphanumeric, underscore, hyphen, dot
    if not all(c.isalnum() or c in "_-." for c in doc_id):
        raise ValueError(f"Invalid characters in document ID: {doc_id}")
    
    # Prevent path traversal
    if ".." in doc_id or doc_id.startswith("."):
        raise ValueError(f"Potentially unsafe document ID: {doc_id}")
    
    return True


def canonicalize(obj: Any) -> str:
    """Canonicalize a JSON-serializable object for hashing.
    
    Args:
        obj: JSON-serializable object.
        
    Returns:
        Canonical JSON string with sorted keys.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_schema_id(doc: Dict[str, Any]) -> str:
    """Compute schema ID for a document.
    
    Args:
        doc: Document dictionary.
        
    Returns:
        SHA-256 hash of the canonical schema.
    """
    schema = extract_schema(doc)
    canonical = canonicalize(schema)
    return hashlib.sha256(canonical.encode()).hexdigest()


def extract_schema(doc: Any) -> Any:
    """Extract structural schema from a document (types, not values).
    
    Args:
        doc: Document or value.
        
    Returns:
        Schema representation.
    """
    if isinstance(doc, dict):
        return {k: extract_schema(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        if doc:
            return [extract_schema(doc[0])]
        return []
    elif isinstance(doc, str):
        return "string"
    elif isinstance(doc, bool):
        return "boolean"
    elif isinstance(doc, int):
        return "integer"
    elif isinstance(doc, float):
        return "number"
    elif doc is None:
        return "null"
    else:
        return "unknown"


def list_collections(root: Path) -> List[str]:
    """List all collections in a store.
    
    Args:
        root: Store root path.
        
    Returns:
        List of collection names.
    """
    collections_path = collections_dir(root)
    if not collections_path.exists():
        return []
    
    return sorted([
        d.name for d in collections_path.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])


def count_documents(root: Path, collection: str) -> int:
    """Count documents in a collection.
    
    Args:
        root: Store root path.
        collection: Collection name.
        
    Returns:
        Number of documents.
    """
    docs = docs_dir(root, collection)
    if not docs.exists():
        return 0
    return len(list(docs.glob("*.json")))


def iter_doc_ids(root: Path, collection: str) -> Iterator[str]:
    """Iterate over document IDs in stable order.
    
    Uses order.ids if available, otherwise falls back to sorted directory listing.
    
    Args:
        root: Store root path.
        collection: Collection name.
        
    Yields:
        Document IDs.
    """
    order_path = order_file(root, collection)
    
    if order_path.exists():
        with open(order_path, "r", encoding="utf-8") as f:
            for line in f:
                doc_id = line.strip()
                if doc_id:
                    yield doc_id
    else:
        # Fallback to directory listing
        docs = docs_dir(root, collection)
        if docs.exists():
            for path in sorted(docs.glob("*.json")):
                yield path.stem
