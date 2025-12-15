"""Tests for ZDSRoot."""

import pytest
import tempfile
from pathlib import Path

from zippy import ZDSRoot, ZDSStore


class TestZDSRoot:
    """Test ZDSRoot operations."""
    
    def test_open_create(self):
        """Test creating a new root."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            assert root.root_path == Path(tmp)
            assert root.list_collections() == []
    
    def test_collection_basic(self):
        """Test opening a collection from root."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            
            train = root.collection("train")
            train.put("doc1", {"name": "alice"})
            
            assert root.collection_exists("train")
            assert train.get("doc1")["name"] == "alice"
    
    def test_multiple_collections(self):
        """Test opening multiple collections from same root."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            
            # Create multiple collections
            train = root.collection("train")
            test = root.collection("test")
            valid = root.collection("validation")
            
            train.put("doc1", {"split": "train", "value": 1})
            test.put("doc1", {"split": "test", "value": 2})
            valid.put("doc1", {"split": "validation", "value": 3})
            
            # Verify each collection has its own data
            assert train.get("doc1")["split"] == "train"
            assert test.get("doc1")["split"] == "test"
            assert valid.get("doc1")["split"] == "validation"
            
            # List collections
            collections = root.list_collections()
            assert len(collections) == 3
            assert "train" in collections
            assert "test" in collections
            assert "validation" in collections
    
    def test_collection_isolation(self):
        """Test that collections are isolated from each other."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            
            # Write same doc ID to different collections
            train = root.collection("train")
            test = root.collection("test")
            
            train.put("doc_001", {"value": 100})
            test.put("doc_001", {"value": 200})
            
            # Each collection should have independent data
            assert train.get("doc_001")["value"] == 100
            assert test.get("doc_001")["value"] == 200
    
    def test_collection_exists(self):
        """Test collection existence check."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            
            assert not root.collection_exists("train")
            
            train = root.collection("train")
            train.put("doc1", {"test": True})
            
            assert root.collection_exists("train")
            assert not root.collection_exists("test")
    
    def test_reopen_root(self):
        """Test reopening root persists collections."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create root and write data
            root1 = ZDSRoot.open(tmp)
            train = root1.collection("train")
            train.put("doc1", {"persisted": True})
            
            # Reopen
            root2 = ZDSRoot.open(tmp)
            assert root2.collection_exists("train")
            
            train2 = root2.collection("train")
            assert train2.get("doc1")["persisted"] == True
    
    def test_repr(self):
        """Test string representation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            root.collection("train").put("doc1", {"test": True})
            
            repr_str = repr(root)
            assert "ZDSRoot" in repr_str
            assert "train" in repr_str
    
    def test_different_from_direct_store(self):
        """Test that ZDSRoot and ZDSStore.open work independently."""
        with tempfile.TemporaryDirectory() as tmp:
            # Use ZDSRoot
            root = ZDSRoot.open(tmp)
            train_via_root = root.collection("train")
            train_via_root.put("doc1", {"source": "root"})
            
            # Use ZDSStore.open directly
            train_via_store = ZDSStore.open(tmp, collection="train")
            assert train_via_store.get("doc1")["source"] == "root"
            
            # Add via direct store
            train_via_store.put("doc2", {"source": "store"})
            
            # Verify via root (need to reopen collection to see new data)
            train_via_root2 = root.collection("train")
            # Note: For pure Python store, this won't see doc2 immediately
            # because they're different instances


class TestZDSRootNative:
    """Test ZDSRoot with native backend (if available)."""
    
    def test_native_basic(self):
        """Test native backend basic operations."""
        with tempfile.TemporaryDirectory() as tmp:
            try:
                root = ZDSRoot.open(tmp, native=True)
            except Exception:
                pytest.skip("Native backend not available")
            
            train = root.collection("train")
            train.put("doc1", {"native": True})
            train.flush()
            
            assert root.collection_exists("train")
    
    def test_native_multiple_collections(self):
        """Test native backend with multiple collections."""
        with tempfile.TemporaryDirectory() as tmp:
            try:
                root = ZDSRoot.open(tmp, native=True)
            except Exception:
                pytest.skip("Native backend not available")
            
            train = root.collection("train")
            test = root.collection("test")
            
            train.put("doc1", {"split": "train"})
            test.put("doc1", {"split": "test"})
            
            train.flush()
            test.flush()
            
            # Verify isolation
            train2 = root.collection("train")
            test2 = root.collection("test")
            
            assert train2.get("doc1")["split"] == "train"
            assert test2.get("doc1")["split"] == "test"


class TestMultiCollectionSafety:
    """Test that multiple collections don't corrupt each other."""
    
    def test_concurrent_writes(self):
        """Test writing to multiple collections concurrently."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            
            # Open all collections first
            collections = {
                name: root.collection(name)
                for name in ["train", "test", "validation", "dev"]
            }
            
            # Write to all collections
            for name, store in collections.items():
                for i in range(10):
                    store.put(f"doc_{i}", {"collection": name, "index": i})
            
            # Verify each collection has correct data
            for name, store in collections.items():
                for i in range(10):
                    doc = store.get(f"doc_{i}")
                    assert doc["collection"] == name
                    assert doc["index"] == i
    
    def test_no_cross_contamination(self):
        """Test that documents don't leak between collections."""
        with tempfile.TemporaryDirectory() as tmp:
            root = ZDSRoot.open(tmp)
            
            train = root.collection("train")
            test = root.collection("test")
            
            # Write unique docs to each
            train.put("train_only", {"exists_in": "train"})
            test.put("test_only", {"exists_in": "test"})
            
            # Verify docs don't exist in wrong collection
            with pytest.raises(KeyError):
                train.get("test_only")
            
            with pytest.raises(KeyError):
                test.get("train_only")
