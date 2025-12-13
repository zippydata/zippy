"""ZDataset - Map-style dataset (random access)."""

from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Union
from pathlib import Path

from .store import ZDSStore


class ZDataset:
    """Map-style dataset with random access.
    
    Compatible with PyTorch DataLoader and HuggingFace datasets API.
    Provides __getitem__ and __len__ for random access by index.
    
    Example:
        >>> store = ZDSStore.open("./my_dataset")
        >>> dataset = ZDataset(store)
        >>> print(dataset[0])  # First document
        >>> print(len(dataset))  # Total count
        >>> 
        >>> # Transformations
        >>> dataset = dataset.select([0, 2, 4])  # Subset
        >>> dataset = dataset.map(lambda x: {"text": x["text"].upper()})
        >>> dataset = dataset.shuffle(seed=42)
    """
    
    def __init__(
        self,
        store: ZDSStore,
        indices: Optional[List[int]] = None,
        transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        """Initialize dataset.
        
        Args:
            store: Underlying ZDSStore.
            indices: Optional index mapping for subsets/shuffling.
            transform: Optional transformation function.
        """
        self._store = store
        self._doc_ids = store.list_doc_ids()
        self._indices = indices
        self._transform = transform
    
    @classmethod
    def from_store(
        cls,
        root: Union[str, Path],
        collection: str = "default",
    ) -> "ZDataset":
        """Create dataset from store path.
        
        Uses FastZDSStore for reading, which supports both JSONL and 
        file-per-doc storage modes.
        
        Args:
            root: Store root path.
            collection: Collection name.
            
        Returns:
            ZDataset instance.
        """
        from .fast_store import FastZDSStore
        store = FastZDSStore.open(root, collection)
        return cls(store)
    
    def __getitem__(self, index: Union[int, slice]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Get document(s) by index.
        
        Args:
            index: Integer index or slice.
            
        Returns:
            Single document or list of documents.
            
        Raises:
            IndexError: If index out of bounds.
        """
        if isinstance(index, slice):
            indices = range(*index.indices(len(self)))
            return [self._get_single(i) for i in indices]
        
        return self._get_single(index)
    
    def _get_single(self, index: int) -> Dict[str, Any]:
        """Get single document by index."""
        if index < 0:
            index = len(self) + index
        
        if index < 0 or index >= len(self):
            raise IndexError(f"Index {index} out of bounds for dataset of size {len(self)}")
        
        # Apply index mapping if present
        if self._indices is not None:
            index = self._indices[index]
        
        doc_id = self._doc_ids[index]
        doc = self._store.get(doc_id)
        
        # Apply transform if present
        if self._transform is not None:
            doc = self._transform(doc)
        
        return doc
    
    def __len__(self) -> int:
        """Get dataset length."""
        if self._indices is not None:
            return len(self._indices)
        return len(self._doc_ids)
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over documents."""
        for i in range(len(self)):
            yield self[i]
    
    def select(self, indices: Sequence[int]) -> "ZDataset":
        """Select a subset by indices.
        
        Args:
            indices: Indices to select.
            
        Returns:
            New ZDataset with subset.
        """
        # Map through existing indices if present
        if self._indices is not None:
            new_indices = [self._indices[i] for i in indices]
        else:
            new_indices = list(indices)
        
        return ZDataset(
            self._store,
            indices=new_indices,
            transform=self._transform,
        )
    
    def shuffle(self, seed: Optional[int] = None) -> "ZDataset":
        """Shuffle the dataset.
        
        Args:
            seed: Random seed for reproducibility.
            
        Returns:
            New shuffled ZDataset.
        """
        import random
        
        rng = random.Random(seed)
        indices = list(range(len(self)))
        rng.shuffle(indices)
        
        return self.select(indices)
    
    def map(
        self,
        function: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> "ZDataset":
        """Apply a transformation function.
        
        Args:
            function: Function to apply to each document.
            
        Returns:
            New ZDataset with transformation.
        """
        # Chain transforms
        if self._transform is not None:
            old_transform = self._transform
            new_transform = lambda x: function(old_transform(x))
        else:
            new_transform = function
        
        return ZDataset(
            self._store,
            indices=self._indices,
            transform=new_transform,
        )
    
    def filter(
        self,
        function: Callable[[Dict[str, Any]], bool],
    ) -> "ZDataset":
        """Filter documents.
        
        Args:
            function: Predicate function returning True to keep.
            
        Returns:
            New filtered ZDataset.
        """
        keep_indices = []
        for i in range(len(self)):
            doc = self[i]
            if function(doc):
                keep_indices.append(i)
        
        return self.select(keep_indices)
    
    def take(self, n: int) -> "ZDataset":
        """Take first n documents.
        
        Args:
            n: Number of documents.
            
        Returns:
            New ZDataset with first n documents.
        """
        return self.select(list(range(min(n, len(self)))))
    
    def skip(self, n: int) -> "ZDataset":
        """Skip first n documents.
        
        Args:
            n: Number of documents to skip.
            
        Returns:
            New ZDataset without first n documents.
        """
        return self.select(list(range(n, len(self))))
    
    def batch(self, batch_size: int) -> Iterator[List[Dict[str, Any]]]:
        """Iterate in batches.
        
        Args:
            batch_size: Number of documents per batch.
            
        Yields:
            Lists of documents.
        """
        for i in range(0, len(self), batch_size):
            yield self[i:i + batch_size]
    
    @property
    def features(self) -> Optional[Dict[str, str]]:
        """Get inferred feature types from first document.
        
        Returns:
            Dict mapping field names to type strings, or None if empty.
        """
        if len(self) == 0:
            return None
        
        doc = self[0]
        features = {}
        
        for k, v in doc.items():
            if isinstance(v, str):
                features[k] = "string"
            elif isinstance(v, bool):
                features[k] = "bool"
            elif isinstance(v, int):
                features[k] = "int64"
            elif isinstance(v, float):
                features[k] = "float64"
            elif isinstance(v, list):
                features[k] = "list"
            elif isinstance(v, dict):
                features[k] = "dict"
            else:
                features[k] = "object"
        
        return features
    
    def __repr__(self) -> str:
        return f"ZDataset(len={len(self)}, features={list(self.features.keys()) if self.features else []})"
