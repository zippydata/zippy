"""Pandas and DataFrame compatibility functions."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .store import ZDSStore


def read_zds(
    path: Union[str, Path],
    collection: str = "default",
    columns: Optional[List[str]] = None,
) -> "pd.DataFrame":
    """Read ZDS collection as a pandas DataFrame.
    
    Requires pandas to be installed.
    
    Args:
        path: Store root path.
        collection: Collection name.
        columns: Optional list of columns to load.
        
    Returns:
        pandas DataFrame with documents as rows.
        
    Raises:
        ImportError: If pandas is not installed.
        
    Example:
        >>> df = read_zds("./my_dataset", collection="train")
        >>> df.head()
           text        label
        0  Hello world     1
        1  Goodbye         0
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for read_zds(). "
            "Install it with: pip install zippy-zds[pandas]"
        )
    
    store = ZDSStore.open(path, collection, create=False)
    
    # Collect documents
    if columns:
        docs = list(store.scan(fields=columns))
    else:
        docs = list(store.scan())
    
    if not docs:
        return pd.DataFrame()
    
    return pd.DataFrame(docs)


def to_zds(
    df: "pd.DataFrame",
    path: Union[str, Path],
    collection: str = "default",
    doc_id_column: Optional[str] = None,
    strict: bool = False,
) -> ZDSStore:
    """Export a pandas DataFrame to ZDS format.
    
    Args:
        df: pandas DataFrame to export.
        path: Store root path.
        collection: Collection name.
        doc_id_column: Column to use as document ID (default: auto-generated).
        strict: Enable strict schema mode.
        
    Returns:
        ZDSStore instance.
        
    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"text": ["hello", "world"], "label": [1, 0]})
        >>> store = to_zds(df, "./output", collection="train")
        >>> len(store)
        2
    """
    store = ZDSStore.open(path, collection, strict=strict)
    
    for idx, row in df.iterrows():
        # Determine document ID
        if doc_id_column and doc_id_column in row:
            doc_id = str(row[doc_id_column])
        else:
            doc_id = f"doc{idx:06d}"
        
        # Convert row to dict, handling pandas types
        doc = {}
        for col in df.columns:
            value = row[col]
            # Convert numpy types to Python types
            if hasattr(value, "item"):
                value = value.item()
            elif hasattr(value, "tolist"):
                value = value.tolist()
            doc[col] = value
        
        store.put(doc_id, doc)
    
    return store


def to_arrow(store: ZDSStore) -> "pa.Table":
    """Convert ZDS store to PyArrow Table.
    
    Requires pyarrow to be installed.
    
    Args:
        store: ZDSStore instance.
        
    Returns:
        PyArrow Table.
        
    Raises:
        ImportError: If pyarrow is not installed.
    """
    try:
        import pyarrow as pa
    except ImportError:
        raise ImportError(
            "pyarrow is required for to_arrow(). "
            "Install it with: pip install zippy-zds[arrow]"
        )
    
    docs = list(store.scan())
    
    if not docs:
        return pa.table({})
    
    # Collect columns
    columns: Dict[str, List[Any]] = {}
    for doc in docs:
        for key, value in doc.items():
            if key not in columns:
                columns[key] = []
            columns[key].append(value)
    
    # Pad missing values
    max_len = max(len(v) for v in columns.values())
    for key in columns:
        while len(columns[key]) < max_len:
            columns[key].append(None)
    
    return pa.table(columns)


def from_arrow(
    table: "pa.Table",
    path: Union[str, Path],
    collection: str = "default",
) -> ZDSStore:
    """Create ZDS store from PyArrow Table.
    
    Args:
        table: PyArrow Table.
        path: Store root path.
        collection: Collection name.
        
    Returns:
        ZDSStore instance.
    """
    store = ZDSStore.open(path, collection)
    
    # Convert to Python dicts
    columns = table.column_names
    
    for i in range(len(table)):
        doc = {}
        for col in columns:
            value = table[col][i].as_py()
            doc[col] = value
        
        doc_id = f"doc{i:06d}"
        store.put(doc_id, doc)
    
    return store
