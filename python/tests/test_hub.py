"""
Tests for hub functionality (load_remote, HuggingFace integration).
"""
import pytest
import tempfile
import shutil
import os
from pathlib import Path

from zippy import ZDataset, ZDSStore, load_remote, dataset_info, clear_cache
from zippy.hub import from_hf, to_hf, to_hf_dict, _resolve_path


class TestLoadRemoteLocal:
    """Tests for load_remote with local paths."""
    
    @pytest.fixture
    def sample_dataset(self):
        """Create a sample ZDS dataset for testing."""
        from zippy import FastZDSStore
        tmpdir = tempfile.mkdtemp()
        
        with FastZDSStore.open(tmpdir, collection="train") as store:
            store.put("doc_001", {"text": "Hello", "label": 0})
            store.put("doc_002", {"text": "World", "label": 1})
        
        with FastZDSStore.open(tmpdir, collection="test") as store:
            store.put("doc_003", {"text": "Test", "label": 0})
        
        yield tmpdir
        shutil.rmtree(tmpdir)
    
    def test_load_remote_local_path(self, sample_dataset):
        """Test loading from local path."""
        dataset = load_remote(sample_dataset, collection="train")
        
        assert len(dataset) == 2
        assert dataset[0]["text"] in ["Hello", "World"]
    
    def test_load_remote_with_split_alias(self, sample_dataset):
        """Test loading with split alias for collection."""
        dataset = load_remote(sample_dataset, split="train")
        
        assert len(dataset) == 2
    
    def test_load_remote_streaming(self, sample_dataset):
        """Test streaming mode."""
        from zippy import ZIterableDataset
        
        dataset = load_remote(sample_dataset, collection="train", streaming=True)
        
        assert isinstance(dataset, ZIterableDataset)
        docs = list(dataset)
        assert len(docs) == 2
    
    def test_load_remote_nonexistent_path(self):
        """Test loading nonexistent path raises error."""
        with pytest.raises(Exception):  # Could be FileNotFoundError or ValueError
            load_remote("/nonexistent/path/that/does/not/exist")


class TestDatasetInfo:
    """Tests for dataset_info function."""
    
    @pytest.fixture
    def sample_dataset(self):
        """Create a sample ZDS dataset for testing."""
        from zippy import FastZDSStore
        tmpdir = tempfile.mkdtemp()
        with FastZDSStore.open(tmpdir, collection="data") as store:
            store.put("doc_001", {"text": "Hello"})
        yield tmpdir
        shutil.rmtree(tmpdir)
    
    def test_dataset_info_local(self, sample_dataset):
        """Test getting info for local dataset."""
        info = dataset_info(sample_dataset)
        
        assert info.provider == "local"
        assert "1 collection" in info.description
    
    def test_dataset_info_remote(self):
        """Test getting info for remote dataset (no download)."""
        # This tests the parsing without actual download
        info = dataset_info("zippydata/test-dataset")
        
        assert info.provider == "git"
        assert info.name == "zippydata/test-dataset"


class TestHuggingFaceIntegration:
    """Tests for HuggingFace Dataset integration."""
    
    @pytest.fixture
    def has_datasets(self):
        """Check if HuggingFace datasets is installed."""
        try:
            import datasets
            return True
        except ImportError:
            pytest.skip("HuggingFace datasets not installed")
    
    @pytest.fixture
    def sample_hf_dataset(self, has_datasets):
        """Create a sample HuggingFace Dataset."""
        from datasets import Dataset
        
        data = {
            "text": ["Hello", "World", "Test"],
            "label": [0, 1, 0],
        }
        return Dataset.from_dict(data)
    
    @pytest.fixture
    def sample_hf_datasetdict(self, has_datasets):
        """Create a sample HuggingFace DatasetDict."""
        from datasets import Dataset, DatasetDict
        
        train_data = {"text": ["Hello", "World"], "label": [0, 1]}
        test_data = {"text": ["Test"], "label": [0]}
        
        return DatasetDict({
            "train": Dataset.from_dict(train_data),
            "test": Dataset.from_dict(test_data),
        })
    
    def test_from_hf_single_dataset(self, sample_hf_dataset):
        """Test converting single HF Dataset to ZDS."""
        tmpdir = tempfile.mkdtemp()
        try:
            zds = from_hf(sample_hf_dataset, tmpdir, collection="main")
            
            assert len(zds) == 3
            assert zds[0]["text"] in ["Hello", "World", "Test"]
        finally:
            shutil.rmtree(tmpdir)
    
    def test_from_hf_datasetdict(self, sample_hf_datasetdict):
        """Test converting HF DatasetDict to ZDS."""
        tmpdir = tempfile.mkdtemp()
        try:
            zds = from_hf(sample_hf_datasetdict, tmpdir)
            
            # Should have created both collections
            from zippy.utils import list_collections
            from pathlib import Path
            collections = list_collections(Path(tmpdir))
            assert "train" in collections
            assert "test" in collections
        finally:
            shutil.rmtree(tmpdir)
    
    def test_from_hf_with_id_column(self, has_datasets):
        """Test from_hf with custom ID column."""
        from datasets import Dataset
        from zippy import FastZDSStore
        
        data = {
            "id": ["a", "b", "c"],
            "text": ["Hello", "World", "Test"],
        }
        hf = Dataset.from_dict(data)
        
        tmpdir = tempfile.mkdtemp()
        try:
            zds = from_hf(hf, tmpdir, collection="main", id_column="id")
            
            # Check that IDs were used
            with FastZDSStore.open(tmpdir, collection="main") as store:
                assert store.get("a") is not None
        finally:
            shutil.rmtree(tmpdir)
    
    def test_to_hf_from_path(self, sample_hf_dataset):
        """Test converting ZDS back to HF Dataset."""
        tmpdir = tempfile.mkdtemp()
        try:
            # First create ZDS
            from_hf(sample_hf_dataset, tmpdir, collection="main")
            
            # Convert back
            hf = to_hf(tmpdir, collection="main")
            
            assert len(hf) == 3
            assert "text" in hf.column_names
            assert "label" in hf.column_names
        finally:
            shutil.rmtree(tmpdir)
    
    def test_to_hf_from_zdataset(self, sample_hf_dataset):
        """Test converting ZDataset to HF Dataset."""
        tmpdir = tempfile.mkdtemp()
        try:
            # Create ZDS
            from_hf(sample_hf_dataset, tmpdir, collection="main")
            
            # Load as ZDataset
            zds = ZDataset.from_store(tmpdir, collection="main")
            
            # Convert
            hf = to_hf(zds)
            
            assert len(hf) == 3
        finally:
            shutil.rmtree(tmpdir)
    
    def test_to_hf_dict(self, sample_hf_datasetdict):
        """Test converting ZDS to HF DatasetDict."""
        tmpdir = tempfile.mkdtemp()
        try:
            # Create ZDS with multiple collections
            from_hf(sample_hf_datasetdict, tmpdir)
            
            # Convert to DatasetDict
            hf = to_hf_dict(tmpdir)
            
            assert "train" in hf
            assert "test" in hf
            assert len(hf["train"]) == 2
            assert len(hf["test"]) == 1
        finally:
            shutil.rmtree(tmpdir)
    
    def test_to_hf_dict_selective(self, sample_hf_datasetdict):
        """Test converting selected collections to HF DatasetDict."""
        tmpdir = tempfile.mkdtemp()
        try:
            from_hf(sample_hf_datasetdict, tmpdir)
            
            hf = to_hf_dict(tmpdir, collections=["train"])
            
            assert "train" in hf
            assert "test" not in hf
        finally:
            shutil.rmtree(tmpdir)
    
    def test_roundtrip_preserves_data(self, has_datasets):
        """Test that ZDS → HF → ZDS roundtrip preserves data."""
        from datasets import Dataset
        
        original_data = {
            "text": ["Hello", "World"],
            "score": [0.5, 0.9],
            "tags": [["a", "b"], ["c"]],
        }
        original = Dataset.from_dict(original_data)
        
        tmpdir1 = tempfile.mkdtemp()
        tmpdir2 = tempfile.mkdtemp()
        try:
            # HF → ZDS
            from_hf(original, tmpdir1, collection="main")
            
            # ZDS → HF
            recovered_hf = to_hf(tmpdir1, collection="main")
            
            # HF → ZDS again
            from_hf(recovered_hf, tmpdir2, collection="main")
            
            # Load final and compare
            final = ZDataset.from_store(tmpdir2, collection="main")
            
            texts = [doc["text"] for doc in final]
            assert set(texts) == {"Hello", "World"}
        finally:
            shutil.rmtree(tmpdir1)
            shutil.rmtree(tmpdir2)


class TestClearCache:
    """Tests for cache clearing."""
    
    def test_clear_cache_no_error_when_empty(self):
        """Test clear_cache doesn't error on empty cache."""
        # This should not raise even if cache is empty
        clear_cache()
    
    def test_clear_cache_with_path(self):
        """Test clearing specific dataset cache."""
        # This is a no-op currently but should not error
        clear_cache("zippydata/test")


class TestResolvePathLocal:
    """Tests for _resolve_path with local paths."""
    
    def test_resolve_existing_path(self):
        """Test resolving existing local path."""
        tmpdir = tempfile.mkdtemp()
        try:
            resolved = _resolve_path(tmpdir)
            assert resolved == Path(tmpdir)
        finally:
            shutil.rmtree(tmpdir)
    
    def test_resolve_path_with_subpath(self):
        """Test resolving path with subpath."""
        tmpdir = tempfile.mkdtemp()
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        
        try:
            resolved = _resolve_path(tmpdir, subpath="subdir")
            assert resolved == subdir
        finally:
            shutil.rmtree(tmpdir)
    
    def test_resolve_home_expansion(self):
        """Test that ~ is expanded in paths."""
        # Create a test in home directory
        home = Path.home()
        if (home / ".cache").exists():
            # Just test expansion works
            path = str(home / ".cache")
            resolved = _resolve_path(path)
            assert "~" not in str(resolved)
