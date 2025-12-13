"""Tests for ZIterableDataset."""

import pytest
import tempfile
from collections import Counter

from zippy import ZDSStore, ZIterableDataset


class TestZIterableDataset:
    """Test ZIterableDataset (streaming) operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ZDSStore.open(self.tmp.name)
        
        # Add test documents
        for i in range(100):
            self.store.put(f"doc{i:03d}", {
                "id": i,
                "name": f"user_{i}",
                "category": ["A", "B", "C"][i % 3],
            })
        
        self.dataset = ZIterableDataset(self.store)
    
    def teardown_method(self):
        """Clean up."""
        self.tmp.cleanup()
    
    def test_iter(self):
        """Test basic iteration."""
        docs = list(self.dataset)
        assert len(docs) == 100
    
    def test_shuffle(self):
        """Test shuffle buffer."""
        shuffled = self.dataset.shuffle(buffer_size=10, seed=42)
        docs = list(shuffled)
        
        assert len(docs) == 100
        
        # All documents should be present
        ids = {d["id"] for d in docs}
        assert ids == set(range(100))
        
        # With seed, should be deterministic
        shuffled2 = self.dataset.shuffle(buffer_size=10, seed=42)
        docs2 = list(shuffled2)
        
        for d1, d2 in zip(docs, docs2):
            assert d1["id"] == d2["id"]
    
    def test_shuffle_buffer_effect(self):
        """Test that shuffle buffer actually shuffles."""
        # Sequential
        sequential = list(self.dataset)
        sequential_ids = [d["id"] for d in sequential]
        
        # Shuffled
        shuffled = list(self.dataset.shuffle(buffer_size=50, seed=42))
        shuffled_ids = [d["id"] for d in shuffled]
        
        # Should be different order
        assert sequential_ids != shuffled_ids
        
        # But same elements
        assert set(sequential_ids) == set(shuffled_ids)
    
    def test_map(self):
        """Test map transformation."""
        mapped = self.dataset.map(lambda x: {**x, "upper_name": x["name"].upper()})
        
        for doc in mapped:
            assert "upper_name" in doc
            assert doc["upper_name"] == doc["name"].upper()
            break  # Just check first
    
    def test_filter(self):
        """Test filtering."""
        filtered = self.dataset.filter(lambda x: x["category"] == "A")
        docs = list(filtered)
        
        # Should have ~33 documents (100/3)
        assert len(docs) == 34  # ceil(100/3)
        
        for doc in docs:
            assert doc["category"] == "A"
    
    def test_take(self):
        """Test taking first n."""
        taken = list(self.dataset.take(5))
        assert len(taken) == 5
    
    def test_skip(self):
        """Test skipping first n."""
        skipped = list(self.dataset.skip(95))
        assert len(skipped) == 5
    
    def test_batch(self):
        """Test batching."""
        batches = list(self.dataset.batch(30))
        assert len(batches) == 4  # 30 + 30 + 30 + 10
        assert len(batches[0]) == 30
        assert len(batches[-1]) == 10
    
    def test_chained_operations(self):
        """Test chaining operations."""
        result = (
            self.dataset
            .filter(lambda x: x["id"] < 50)
            .map(lambda x: {**x, "processed": True})
            .shuffle(buffer_size=10, seed=42)
        )
        
        docs = list(result)
        assert len(docs) == 50
        
        for doc in docs:
            assert doc["id"] < 50
            assert doc["processed"] is True
    
    def test_from_store(self):
        """Test from_store factory."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            for i in range(10):
                store.put(f"doc{i}", {"id": i})
            
            dataset = ZIterableDataset.from_store(tmp)
            docs = list(dataset)
            assert len(docs) == 10
    
    def test_shuffle_preserves_all_elements(self):
        """Verify shuffle doesn't lose or duplicate elements."""
        shuffled = self.dataset.shuffle(buffer_size=20, seed=42)
        docs = list(shuffled)
        
        ids = [d["id"] for d in docs]
        
        # Check no duplicates
        assert len(ids) == len(set(ids))
        
        # Check all present
        assert set(ids) == set(range(100))
    
    def test_multiple_iterations(self):
        """Test that dataset can be iterated multiple times."""
        first_pass = list(self.dataset)
        second_pass = list(self.dataset)
        
        assert len(first_pass) == len(second_pass) == 100
        
        # Without shuffle, should be same order
        for d1, d2 in zip(first_pass, second_pass):
            assert d1["id"] == d2["id"]
