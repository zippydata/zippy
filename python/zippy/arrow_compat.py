"""Apache Arrow compatibility for zero-copy data exchange."""

from typing import Any, Dict, Iterator, List, Optional, Union
from pathlib import Path

from .store import ZDSStore


def to_arrow_batch_reader(
    store: ZDSStore,
    batch_size: int = 1000,
) -> "pa.RecordBatchReader":
    """Create Arrow RecordBatchReader for streaming reads.
    
    Enables zero-copy integration with DuckDB, Polars, and other Arrow-native tools.
    
    Args:
        store: ZDSStore instance.
        batch_size: Number of documents per batch.
        
    Returns:
        PyArrow RecordBatchReader.
        
    Raises:
        ImportError: If pyarrow is not installed.
        
    Example:
        >>> reader = to_arrow_batch_reader(store)
        >>> for batch in reader:
        ...     # Process batch
        ...     pass
    """
    try:
        import pyarrow as pa
    except ImportError:
        raise ImportError(
            "pyarrow is required for Arrow integration. "
            "Install it with: pip install zippy-zds[arrow]"
        )
    
    def batch_generator() -> Iterator[pa.RecordBatch]:
        docs: List[Dict[str, Any]] = []
        schema: Optional[pa.Schema] = None
        
        for doc in store.scan():
            docs.append(doc)
            
            if len(docs) >= batch_size:
                batch, schema = _docs_to_batch(docs, schema)
                yield batch
                docs = []
        
        if docs:
            batch, _ = _docs_to_batch(docs, schema)
            yield batch
    
    # Get schema from first document
    try:
        first_doc = next(iter(store.scan()))
        schema = _infer_schema(first_doc)
    except StopIteration:
        schema = pa.schema([])
    
    return pa.RecordBatchReader.from_batches(schema, batch_generator())


def _docs_to_batch(
    docs: List[Dict[str, Any]],
    schema: Optional["pa.Schema"] = None,
) -> tuple["pa.RecordBatch", "pa.Schema"]:
    """Convert documents to Arrow RecordBatch."""
    import pyarrow as pa
    
    if not docs:
        if schema is None:
            schema = pa.schema([])
        return pa.record_batch([], schema=schema), schema
    
    # Collect columns
    columns: Dict[str, List[Any]] = {}
    for doc in docs:
        for key, value in doc.items():
            if key not in columns:
                columns[key] = [None] * (len(docs) - 1)
            columns[key].append(value)
    
    # Pad missing values
    for key in columns:
        while len(columns[key]) < len(docs):
            columns[key].append(None)
    
    # Build arrays
    arrays = []
    fields = []
    
    for name, values in columns.items():
        arr = pa.array(values)
        arrays.append(arr)
        fields.append(pa.field(name, arr.type))
    
    if schema is None:
        schema = pa.schema(fields)
    
    return pa.record_batch(arrays, names=list(columns.keys())), schema


def _infer_schema(doc: Dict[str, Any]) -> "pa.Schema":
    """Infer Arrow schema from a document."""
    import pyarrow as pa
    
    fields = []
    for key, value in doc.items():
        if isinstance(value, str):
            dtype = pa.string()
        elif isinstance(value, bool):
            dtype = pa.bool_()
        elif isinstance(value, int):
            dtype = pa.int64()
        elif isinstance(value, float):
            dtype = pa.float64()
        elif isinstance(value, list):
            if value and isinstance(value[0], str):
                dtype = pa.list_(pa.string())
            elif value and isinstance(value[0], (int, float)):
                dtype = pa.list_(pa.float64())
            else:
                dtype = pa.string()  # Fallback: serialize as JSON
        elif isinstance(value, dict):
            dtype = pa.string()  # Serialize nested objects as JSON
        else:
            dtype = pa.string()
        
        fields.append(pa.field(key, dtype))
    
    return pa.schema(fields)


def query_with_duckdb(
    store: ZDSStore,
    query: str,
    alias: str = "zds",
) -> "duckdb.DuckDBPyRelation":
    """Query ZDS store using DuckDB SQL.
    
    Args:
        store: ZDSStore instance.
        query: SQL query (use alias to reference the table).
        alias: Table alias in the query.
        
    Returns:
        DuckDB relation with query results.
        
    Raises:
        ImportError: If duckdb is not installed.
        
    Example:
        >>> result = query_with_duckdb(
        ...     store,
        ...     "SELECT text, label FROM zds WHERE label = 1",
        ...     alias="zds"
        ... )
        >>> result.fetchall()
    """
    try:
        import duckdb
        import pyarrow as pa
    except ImportError:
        raise ImportError(
            "duckdb and pyarrow are required for SQL queries. "
            "Install them with: pip install zippy-zds[duckdb,arrow]"
        )
    
    # Create Arrow table
    from .pandas_compat import to_arrow
    table = to_arrow(store)
    
    # Query with DuckDB
    conn = duckdb.connect()
    conn.register(alias, table)
    
    return conn.execute(query)
