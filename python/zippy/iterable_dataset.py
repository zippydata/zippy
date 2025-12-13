"""ZIterableDataset - Streaming dataset with shuffle buffer."""

import random
from typing import Any, Callable, Dict, Iterator, List, Optional, Union
from pathlib import Path

from .store import ZDSStore


class ZIterableDataset:
    """Iterable (streaming) dataset with shuffle buffer.
    
    Compatible with PyTorch IterableDataset and HuggingFace iterable datasets.
    Supports streaming iteration without loading all data into memory.
    
    The shuffle buffer provides approximate shuffling by maintaining a buffer
    of documents and randomly sampling from it. This is the same approach
    used by HuggingFace's iterable datasets for efficient shuffling.
    
    Example:
        >>> store = ZDSStore.open("./my_dataset")
        >>> dataset = ZIterableDataset(store)
        >>> 
        >>> # Simple iteration
        >>> for doc in dataset:
        ...     print(doc)
        >>> 
        >>> # With shuffle buffer
        >>> for doc in dataset.shuffle(buffer_size=1000, seed=42):
        ...     print(doc)
        >>> 
        >>> # With transformations
        >>> dataset = dataset.map(lambda x: {"text": x["text"].upper()})
        >>> dataset = dataset.filter(lambda x: len(x["text"]) > 10)
    """
    
    def __init__(
        self,
        store: ZDSStore,
        buffer_size: int = 0,
        seed: Optional[int] = None,
        transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ):
        """Initialize iterable dataset.
        
        Args:
            store: Underlying ZDSStore.
            buffer_size: Shuffle buffer size (0 = no shuffling).
            seed: Random seed for shuffling.
            transform: Optional transformation function.
            filter_fn: Optional filter predicate.
        """
        self._store = store
        self._buffer_size = buffer_size
        self._seed = seed
        self._transform = transform
        self._filter_fn = filter_fn
    
    @classmethod
    def from_store(
        cls,
        root: Union[str, Path],
        collection: str = "default",
    ) -> "ZIterableDataset":
        """Create dataset from store path.
        
        Args:
            root: Store root path.
            collection: Collection name.
            
        Returns:
            ZIterableDataset instance.
        """
        store = ZDSStore.open(root, collection)
        return cls(store)
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over documents.
        
        If buffer_size > 0, uses a shuffle buffer for approximate shuffling.
        """
        if self._buffer_size > 0:
            yield from self._shuffled_iter()
        else:
            yield from self._sequential_iter()
    
    def _sequential_iter(self) -> Iterator[Dict[str, Any]]:
        """Sequential iteration without shuffling."""
        for doc in self._store.scan():
            # Apply filter
            if self._filter_fn is not None and not self._filter_fn(doc):
                continue
            
            # Apply transform
            if self._transform is not None:
                doc = self._transform(doc)
            
            yield doc
    
    def _shuffled_iter(self) -> Iterator[Dict[str, Any]]:
        """Shuffled iteration using a buffer.
        
        Algorithm:
        1. Fill buffer with first N documents
        2. For each remaining document:
           a. Randomly select and yield one from buffer
           b. Replace it with the new document
        3. Shuffle and yield remaining buffer contents
        """
        rng = random.Random(self._seed)
        buffer: List[Dict[str, Any]] = []
        
        source = self._store.scan()
        
        # Fill initial buffer
        for doc in source:
            # Apply filter
            if self._filter_fn is not None and not self._filter_fn(doc):
                continue
            
            # Apply transform
            if self._transform is not None:
                doc = self._transform(doc)
            
            buffer.append(doc)
            
            if len(buffer) >= self._buffer_size:
                break
        
        # Yield from buffer while refilling
        for doc in source:
            # Apply filter
            if self._filter_fn is not None and not self._filter_fn(doc):
                continue
            
            # Apply transform
            if self._transform is not None:
                doc = self._transform(doc)
            
            # Sample from buffer
            idx = rng.randint(0, len(buffer) - 1)
            yield buffer[idx]
            buffer[idx] = doc
        
        # Yield remaining buffer (shuffled)
        rng.shuffle(buffer)
        yield from buffer
    
    def shuffle(
        self,
        buffer_size: int = 1000,
        seed: Optional[int] = None,
    ) -> "ZIterableDataset":
        """Enable shuffling with a buffer.
        
        Args:
            buffer_size: Size of shuffle buffer.
            seed: Random seed for reproducibility.
            
        Returns:
            New ZIterableDataset with shuffling enabled.
        """
        return ZIterableDataset(
            self._store,
            buffer_size=buffer_size,
            seed=seed,
            transform=self._transform,
            filter_fn=self._filter_fn,
        )
    
    def map(
        self,
        function: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> "ZIterableDataset":
        """Apply a transformation function.
        
        Args:
            function: Function to apply to each document.
            
        Returns:
            New ZIterableDataset with transformation.
        """
        # Chain transforms
        if self._transform is not None:
            old_transform = self._transform
            new_transform = lambda x: function(old_transform(x))
        else:
            new_transform = function
        
        return ZIterableDataset(
            self._store,
            buffer_size=self._buffer_size,
            seed=self._seed,
            transform=new_transform,
            filter_fn=self._filter_fn,
        )
    
    def filter(
        self,
        function: Callable[[Dict[str, Any]], bool],
    ) -> "ZIterableDataset":
        """Filter documents.
        
        Args:
            function: Predicate function returning True to keep.
            
        Returns:
            New filtered ZIterableDataset.
        """
        # Chain filters
        if self._filter_fn is not None:
            old_filter = self._filter_fn
            new_filter = lambda x: old_filter(x) and function(x)
        else:
            new_filter = function
        
        return ZIterableDataset(
            self._store,
            buffer_size=self._buffer_size,
            seed=self._seed,
            transform=self._transform,
            filter_fn=new_filter,
        )
    
    def take(self, n: int) -> Iterator[Dict[str, Any]]:
        """Take first n documents.
        
        Args:
            n: Number of documents to take.
            
        Yields:
            Up to n documents.
        """
        count = 0
        for doc in self:
            if count >= n:
                break
            yield doc
            count += 1
    
    def skip(self, n: int) -> Iterator[Dict[str, Any]]:
        """Skip first n documents.
        
        Args:
            n: Number of documents to skip.
            
        Yields:
            Documents after the first n.
        """
        for i, doc in enumerate(self):
            if i >= n:
                yield doc
    
    def batch(self, batch_size: int) -> Iterator[List[Dict[str, Any]]]:
        """Iterate in batches.
        
        Args:
            batch_size: Number of documents per batch.
            
        Yields:
            Lists of documents.
        """
        batch: List[Dict[str, Any]] = []
        
        for doc in self:
            batch.append(doc)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        if batch:
            yield batch
    
    def __repr__(self) -> str:
        shuffle_info = f", shuffle_buffer={self._buffer_size}" if self._buffer_size > 0 else ""
        return f"ZIterableDataset(collection={self._store.collection!r}{shuffle_info})"
