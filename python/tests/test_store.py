"""Tests for ZDSStore."""

import json
import pytest
import tempfile
from pathlib import Path

from zippy import ZDSStore


class TestZDSStore:
    """Test ZDSStore operations."""
    
    def test_open_create(self):
        """Test creating a new store."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp, collection="test")
            assert store.count() == 0
            assert store.collection == "test"
    
    def test_open_existing(self):
        """Test opening an existing store."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create
            store1 = ZDSStore.open(tmp, collection="test")
            store1.put("doc1", {"name": "alice"})
            
            # Reopen
            store2 = ZDSStore.open(tmp, collection="test")
            assert store2.count() == 1
            assert store2.get("doc1")["name"] == "alice"
    
    def test_put_get(self):
        """Test basic put/get operations."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            doc = {"text": "hello world", "label": 1}
            store.put("doc1", doc)
            
            result = store.get("doc1")
            assert result == doc
    
    def test_get_not_found(self):
        """Test getting non-existent document."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            with pytest.raises(KeyError):
                store.get("nonexistent")
    
    def test_delete(self):
        """Test delete operation."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            store.put("doc1", {"test": True})
            
            assert store.exists("doc1")
            store.delete("doc1")
            assert not store.exists("doc1")
    
    def test_delete_not_found(self):
        """Test deleting non-existent document."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            with pytest.raises(KeyError):
                store.delete("nonexistent")
    
    def test_scan(self):
        """Test scanning all documents."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            store.put("doc1", {"name": "alice"})
            store.put("doc2", {"name": "bob"})
            store.put("doc3", {"name": "charlie"})
            
            docs = list(store.scan())
            assert len(docs) == 3
            names = {d["name"] for d in docs}
            assert names == {"alice", "bob", "charlie"}
    
    def test_scan_with_fields(self):
        """Test scanning with projection."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            store.put("doc1", {"name": "alice", "age": 30, "city": "NYC"})
            
            docs = list(store.scan(fields=["name", "age"]))
            assert len(docs) == 1
            assert "name" in docs[0]
            assert "age" in docs[0]
            assert "city" not in docs[0]
    
    def test_scan_with_predicate(self):
        """Test scanning with predicate."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            store.put("doc1", {"name": "alice", "active": True})
            store.put("doc2", {"name": "bob", "active": False})
            store.put("doc3", {"name": "charlie", "active": True})
            
            docs = list(store.scan(predicate={"active": True}))
            assert len(docs) == 2
            names = {d["name"] for d in docs}
            assert names == {"alice", "charlie"}
    
    def test_list_doc_ids(self):
        """Test listing document IDs."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            store.put("doc1", {"test": 1})
            store.put("doc2", {"test": 2})
            
            ids = store.list_doc_ids()
            assert set(ids) == {"doc1", "doc2"}
    
    def test_count(self):
        """Test document count."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            assert store.count() == 0
            store.put("doc1", {"test": 1})
            assert store.count() == 1
            store.put("doc2", {"test": 2})
            assert store.count() == 2
            store.delete("doc1")
            assert store.count() == 1
    
    def test_strict_mode(self):
        """Test strict schema mode."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp, strict=True)
            
            # First document sets schema
            store.put("doc1", {"name": "alice", "age": 30})
            
            # Same schema works
            store.put("doc2", {"name": "bob", "age": 25})
            
            # Different schema fails
            with pytest.raises(ValueError, match="Schema mismatch"):
                store.put("doc3", {"different": "schema"})
    
    def test_invalid_doc_id(self):
        """Test invalid document ID rejection."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            with pytest.raises(ValueError):
                store.put("", {"test": True})
            
            with pytest.raises(ValueError):
                store.put("../evil", {"test": True})
            
            with pytest.raises(ValueError):
                store.put(".hidden", {"test": True})
    
    def test_dunder_methods(self):
        """Test __contains__, __getitem__, etc."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            
            # __setitem__
            store["doc1"] = {"test": True}
            
            # __contains__
            assert "doc1" in store
            assert "doc2" not in store
            
            # __getitem__
            assert store["doc1"]["test"] is True
            
            # __len__
            assert len(store) == 1
            
            # __delitem__
            del store["doc1"]
            assert "doc1" not in store
    
    def test_to_dataset(self):
        """Test conversion to ZDataset."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            store.put("doc1", {"test": 1})
            
            dataset = store.to_dataset()
            assert len(dataset) == 1
    
    def test_to_iterable_dataset(self):
        """Test conversion to ZIterableDataset."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            store.put("doc1", {"test": 1})
            
            dataset = store.to_iterable_dataset()
            docs = list(dataset)
            assert len(docs) == 1
