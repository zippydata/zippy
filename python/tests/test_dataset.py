"""Tests for ZDataset."""

import pytest
import tempfile

from zippy import ZDSStore, ZDataset


class TestZDataset:
    """Test ZDataset (map-style) operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ZDSStore.open(self.tmp.name)
        
        # Add test documents
        for i in range(10):
            self.store.put(f"doc{i:02d}", {
                "id": i,
                "name": f"user_{i}",
                "score": i * 10,
            })
        
        self.dataset = ZDataset(self.store)
    
    def teardown_method(self):
        """Clean up."""
        self.tmp.cleanup()
    
    def test_len(self):
        """Test dataset length."""
        assert len(self.dataset) == 10
    
    def test_getitem_int(self):
        """Test integer indexing."""
        doc = self.dataset[0]
        assert doc["id"] == 0
        assert doc["name"] == "user_0"
    
    def test_getitem_negative(self):
        """Test negative indexing."""
        doc = self.dataset[-1]
        assert doc["id"] == 9
    
    def test_getitem_slice(self):
        """Test slice indexing."""
        docs = self.dataset[0:3]
        assert len(docs) == 3
        assert docs[0]["id"] == 0
        assert docs[2]["id"] == 2
    
    def test_getitem_out_of_bounds(self):
        """Test out of bounds access."""
        with pytest.raises(IndexError):
            _ = self.dataset[100]
    
    def test_iter(self):
        """Test iteration."""
        docs = list(self.dataset)
        assert len(docs) == 10
    
    def test_select(self):
        """Test selecting subset."""
        subset = self.dataset.select([0, 2, 4])
        assert len(subset) == 3
        assert subset[0]["id"] == 0
        assert subset[1]["id"] == 2
        assert subset[2]["id"] == 4
    
    def test_shuffle(self):
        """Test shuffling."""
        shuffled = self.dataset.shuffle(seed=42)
        assert len(shuffled) == 10
        
        # With seed, should be deterministic
        shuffled2 = self.dataset.shuffle(seed=42)
        for i in range(10):
            assert shuffled[i]["id"] == shuffled2[i]["id"]
        
        # Different seed should give different order
        shuffled3 = self.dataset.shuffle(seed=123)
        different = False
        for i in range(10):
            if shuffled[i]["id"] != shuffled3[i]["id"]:
                different = True
                break
        assert different
    
    def test_map(self):
        """Test map transformation."""
        mapped = self.dataset.map(lambda x: {**x, "score": x["score"] * 2})
        
        assert mapped[0]["score"] == 0
        assert mapped[1]["score"] == 20
    
    def test_filter(self):
        """Test filtering."""
        filtered = self.dataset.filter(lambda x: x["id"] % 2 == 0)
        assert len(filtered) == 5
        
        for doc in filtered:
            assert doc["id"] % 2 == 0
    
    def test_take(self):
        """Test taking first n."""
        taken = self.dataset.take(3)
        assert len(taken) == 3
    
    def test_skip(self):
        """Test skipping first n."""
        skipped = self.dataset.skip(7)
        assert len(skipped) == 3
    
    def test_batch(self):
        """Test batching."""
        batches = list(self.dataset.batch(3))
        assert len(batches) == 4  # 3 + 3 + 3 + 1
        assert len(batches[0]) == 3
        assert len(batches[3]) == 1
    
    def test_features(self):
        """Test feature inference."""
        features = self.dataset.features
        assert "id" in features
        assert "name" in features
        assert "score" in features
    
    def test_chained_operations(self):
        """Test chaining multiple operations."""
        result = (
            self.dataset
            .filter(lambda x: x["id"] < 6)
            .map(lambda x: {**x, "doubled": x["score"] * 2})
            .shuffle(seed=42)
            .take(3)
        )
        
        assert len(result) == 3
        for doc in result:
            assert doc["id"] < 6
            assert "doubled" in doc
    
    def test_from_store(self):
        """Test from_store factory."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ZDSStore.open(tmp)
            store.put("doc1", {"test": True})
            
            dataset = ZDataset.from_store(tmp)
            assert len(dataset) == 1
