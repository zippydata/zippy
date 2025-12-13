"""DuckDB integration for ZDS.

Provides functions to:
- Query ZDS data using SQL
- Export query results to ZDS
- Register ZDS collections as virtual tables

Requires: pip install duckdb
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

from .store import ZDSStore
from .utils import validate_doc_id

if TYPE_CHECKING:
    import duckdb


def _get_duckdb():
    """Import duckdb, raising helpful error if not installed."""
    try:
        import duckdb
        return duckdb
    except ImportError:
        raise ImportError(
            "DuckDB is required for this feature. "
            "Install it with: pip install duckdb"
        )


class ZDSTableFunction:
    """DuckDB table function for reading ZDS collections."""
    
    def __init__(
        self,
        path: Union[str, Path],
        collection: str = "default",
        fields: Optional[list[str]] = None
    ):
        self.store = ZDSStore.open(path, collection=collection)
        self.fields = fields
        self._schema = None
    
    def _infer_schema(self) -> dict[str, str]:
        """Infer DuckDB types from first document."""
        if self._schema is not None:
            return self._schema
        
        type_map = {
            "string": "VARCHAR",
            "int64": "BIGINT",
            "float64": "DOUBLE",
            "bool": "BOOLEAN",
            "list": "JSON",
            "dict": "JSON",
            "null": "VARCHAR"
        }
        
        # Get first doc to infer types
        doc_ids = self.store.list_doc_ids()
        if not doc_ids:
            return {}
        
        doc = self.store.get(doc_ids[0])
        schema = {}
        
        for key, value in doc.items():
            if self.fields and key not in self.fields:
                continue
            
            if value is None:
                dtype = "VARCHAR"
            elif isinstance(value, bool):
                dtype = "BOOLEAN"
            elif isinstance(value, int):
                dtype = "BIGINT"
            elif isinstance(value, float):
                dtype = "DOUBLE"
            elif isinstance(value, str):
                dtype = "VARCHAR"
            elif isinstance(value, (list, dict)):
                dtype = "JSON"
            else:
                dtype = "VARCHAR"
            
            schema[key] = dtype
        
        # Always include _id
        schema["_id"] = "VARCHAR"
        self._schema = schema
        return schema
    
    def __call__(self) -> Iterator[dict[str, Any]]:
        """Yield rows for DuckDB."""
        for doc_id in self.store.list_doc_ids():
            doc = self.store.get(doc_id)
            
            if self.fields:
                row = {k: doc.get(k) for k in self.fields if k in doc}
            else:
                row = dict(doc)
            
            # Add document ID
            row["_id"] = doc_id
            
            # Convert complex types to JSON strings for DuckDB
            for k, v in row.items():
                if isinstance(v, (list, dict)):
                    row[k] = json.dumps(v)
            
            yield row


def register_zds(
    conn: "duckdb.DuckDBPyConnection",
    path: Union[str, Path],
    collection: str = "default",
    view_name: Optional[str] = None,
    fields: Optional[list[str]] = None
) -> None:
    """Register a ZDS collection as a DuckDB view.
    
    Args:
        conn: DuckDB connection
        path: Path to ZDS store
        collection: Collection name
        view_name: Name for the view (defaults to collection name)
        fields: Optional list of fields to include (projection)
    
    Example:
        >>> import duckdb
        >>> conn = duckdb.connect()
        >>> register_zds(conn, "/data/store", "users")
        >>> conn.execute("SELECT * FROM users WHERE age > 30").fetchall()
    """
    duckdb = _get_duckdb()
    
    if view_name is None:
        view_name = collection
    
    # Load data from ZDS
    store = ZDSStore.open(path, collection=collection)
    
    if store.count() == 0:
        raise ValueError(f"Collection '{collection}' is empty or not found")
    
    # Build list of rows for DuckDB
    rows = []
    for doc_id in store.list_doc_ids():
        doc = store.get(doc_id)
        if fields:
            row = {k: doc.get(k) for k in fields if k in doc}
        else:
            row = dict(doc)
        
        # Add document ID
        row["_id"] = doc_id
        
        # Convert complex types to JSON strings
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                row[k] = json.dumps(v)
        
        rows.append(row)
    
    # Convert to format DuckDB can use
    # Try pandas first, fall back to direct SQL
    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        conn.register(f"_zds_{view_name}_data", df)
        conn.execute(f'CREATE OR REPLACE VIEW "{view_name}" AS SELECT * FROM "_zds_{view_name}_data"')
    except ImportError:
        # No pandas - create table directly via INSERT
        if not rows:
            return
        columns = list(rows[0].keys())
        col_defs = ", ".join(f'"{c}" VARCHAR' for c in columns)
        conn.execute(f'CREATE OR REPLACE TABLE "{view_name}" ({col_defs})')
        
        placeholders = ", ".join("?" for _ in columns)
        for row in rows:
            values = [str(row.get(c, "")) for c in columns]
            conn.execute(f'INSERT INTO "{view_name}" VALUES ({placeholders})', values)


def query_zds(
    path: Union[str, Path],
    collection: str,
    sql: str,
    params: Optional[tuple] = None
) -> list[tuple]:
    """Execute SQL query against a ZDS collection.
    
    Args:
        path: Path to ZDS store
        collection: Collection name
        sql: SQL query (use 'data' as table name)
        params: Optional query parameters
    
    Returns:
        List of result tuples
    
    Example:
        >>> results = query_zds("/data/store", "users", 
        ...     "SELECT name, age FROM data WHERE age > 30 ORDER BY age")
    """
    duckdb = _get_duckdb()
    
    conn = duckdb.connect()
    register_zds(conn, path, collection, view_name="data")
    
    if params:
        result = conn.execute(sql, params).fetchall()
    else:
        result = conn.execute(sql).fetchall()
    
    conn.close()
    return result


def query_zds_df(
    path: Union[str, Path],
    collection: str,
    sql: str,
    params: Optional[tuple] = None
):
    """Execute SQL query and return pandas DataFrame.
    
    Args:
        path: Path to ZDS store
        collection: Collection name
        sql: SQL query (use 'data' as table name)
        params: Optional query parameters
    
    Returns:
        pandas DataFrame with query results
    """
    duckdb = _get_duckdb()
    
    conn = duckdb.connect()
    register_zds(conn, path, collection, view_name="data")
    
    if params:
        result = conn.execute(sql, params).df()
    else:
        result = conn.execute(sql).df()
    
    conn.close()
    return result


def export_query_to_zds(
    conn: "duckdb.DuckDBPyConnection",
    sql: str,
    path: Union[str, Path],
    collection: str = "default",
    id_column: Optional[str] = None,
    id_prefix: str = "row"
) -> int:
    """Export DuckDB query results to ZDS.
    
    Args:
        conn: DuckDB connection with source data
        sql: SQL query to export
        path: Path to ZDS store
        collection: Collection name
        id_column: Column to use as document ID (auto-generate if None)
        id_prefix: Prefix for auto-generated IDs
    
    Returns:
        Number of documents exported
    
    Example:
        >>> conn = duckdb.connect()
        >>> conn.execute("CREATE TABLE t AS SELECT * FROM 'data.csv'")
        >>> export_query_to_zds(conn, "SELECT * FROM t WHERE x > 0", 
        ...     "/data/store", "filtered_data")
    """
    store = ZDSStore.open(path, collection=collection)
    
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    
    count = 0
    for i, row in enumerate(result.fetchall()):
        doc = dict(zip(columns, row))
        
        # Determine document ID
        if id_column and id_column in doc:
            doc_id = str(doc[id_column])
        else:
            doc_id = f"{id_prefix}_{i:08d}"
        
        # Validate and store
        if validate_doc_id(doc_id):
            store.put(doc_id, doc)
            count += 1
    
    return count


def copy_to_zds(
    conn: "duckdb.DuckDBPyConnection",
    table_or_query: str,
    path: Union[str, Path],
    collection: str = "default",
    id_column: Optional[str] = None
) -> int:
    """Copy a DuckDB table or query result to ZDS.
    
    Args:
        conn: DuckDB connection
        table_or_query: Table name or SELECT query
        path: Path to ZDS store  
        collection: Collection name
        id_column: Column to use as document ID
    
    Returns:
        Number of documents copied
    """
    # Detect if it's a query or table name
    if table_or_query.strip().upper().startswith("SELECT"):
        sql = table_or_query
    else:
        sql = f'SELECT * FROM "{table_or_query}"'
    
    return export_query_to_zds(conn, sql, path, collection, id_column)


class ZDSConnection:
    """Convenience wrapper for DuckDB + ZDS operations.
    
    Example:
        >>> zds = ZDSConnection("/data/store")
        >>> zds.register("users")
        >>> zds.register("products")
        >>> results = zds.query("SELECT u.name, p.name FROM users u JOIN products p ON ...")
    """
    
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.duckdb = _get_duckdb()
        self.conn = self.duckdb.connect()
        self._registered: set[str] = set()
    
    def register(
        self, 
        collection: str, 
        view_name: Optional[str] = None,
        fields: Optional[list[str]] = None
    ) -> "ZDSConnection":
        """Register a collection as a queryable view."""
        name = view_name or collection
        register_zds(self.conn, self.path, collection, name, fields)
        self._registered.add(name)
        return self
    
    def query(self, sql: str, params: Optional[tuple] = None) -> list[tuple]:
        """Execute SQL query."""
        if params:
            return self.conn.execute(sql, params).fetchall()
        return self.conn.execute(sql).fetchall()
    
    def query_df(self, sql: str, params: Optional[tuple] = None):
        """Execute SQL query and return DataFrame."""
        if params:
            return self.conn.execute(sql, params).df()
        return self.conn.execute(sql).df()
    
    def export(
        self, 
        sql: str, 
        collection: str,
        id_column: Optional[str] = None
    ) -> int:
        """Export query results to a new collection."""
        return export_query_to_zds(
            self.conn, sql, self.path, collection, id_column
        )
    
    def execute(self, sql: str, params: Optional[tuple] = None):
        """Execute arbitrary SQL."""
        if params:
            return self.conn.execute(sql, params)
        return self.conn.execute(sql)
    
    def close(self):
        """Close the connection."""
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# Convenience functions for common operations

def sql(
    path: Union[str, Path],
    collection: str,
    query: str
) -> list[tuple]:
    """Quick SQL query on a ZDS collection.
    
    Example:
        >>> sql("/data", "users", "SELECT * FROM data WHERE age > 25")
    """
    return query_zds(path, collection, query)


def aggregate(
    path: Union[str, Path],
    collection: str,
    group_by: str,
    agg_expr: str
) -> list[tuple]:
    """Quick aggregation on a ZDS collection.
    
    Example:
        >>> aggregate("/data", "sales", "region", "SUM(amount) as total")
    """
    query = f"SELECT {group_by}, {agg_expr} FROM data GROUP BY {group_by}"
    return query_zds(path, collection, query)


def count_where(
    path: Union[str, Path],
    collection: str,
    condition: str
) -> int:
    """Count documents matching a condition.
    
    Example:
        >>> count_where("/data", "users", "age > 30 AND active = true")
    """
    query = f"SELECT COUNT(*) FROM data WHERE {condition}"
    result = query_zds(path, collection, query)
    return result[0][0] if result else 0
