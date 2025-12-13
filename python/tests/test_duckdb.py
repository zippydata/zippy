"""Tests for DuckDB integration."""

import json
import pytest
import tempfile

# Check if DuckDB is available
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

if DUCKDB_AVAILABLE:
    from zippy import ZDSStore
    from zippy.duckdb_compat import (
        register_zds,
        query_zds,
        query_zds_df,
        export_query_to_zds,
        ZDSConnection,
        sql,
        aggregate,
        count_where
    )


@pytest.mark.skipif(not DUCKDB_AVAILABLE, reason="DuckDB not installed")
class TestDuckDBIntegration:
    """Test DuckDB integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ZDSStore.open(self.tmp.name, collection="test")
        
        # Add test documents
        for i in range(100):
            self.store.put(f"doc_{i:03d}", {
                "id": i,
                "name": f"User {i}",
                "age": 20 + (i % 50),
                "score": i * 1.5,
                "active": i % 2 == 0
            })
    
    def teardown_method(self):
        """Clean up."""
        self.tmp.cleanup()
    
    def test_sql_basic(self):
        """Test basic SQL query."""
        results = sql(self.tmp.name, "test", "SELECT COUNT(*) FROM data")
        assert results[0][0] == 100
    
    def test_sql_where(self):
        """Test SQL with WHERE clause."""
        results = sql(self.tmp.name, "test", 
            "SELECT * FROM data WHERE active = true")
        assert len(results) == 50
    
    def test_sql_aggregation(self):
        """Test SQL aggregation."""
        results = sql(self.tmp.name, "test",
            "SELECT AVG(age) as avg_age FROM data")
        assert results[0][0] is not None
    
    def test_aggregate_helper(self):
        """Test aggregate helper function."""
        results = aggregate(self.tmp.name, "test", 
            "active", "COUNT(*) as cnt, AVG(score) as avg_score")
        assert len(results) == 2  # true and false groups
    
    def test_count_where(self):
        """Test count_where helper."""
        count = count_where(self.tmp.name, "test", "age > 40")
        assert count > 0
        assert count < 100
    
    def test_query_zds_with_params(self):
        """Test parameterized query."""
        results = query_zds(self.tmp.name, "test",
            "SELECT * FROM data WHERE age > ? AND active = ?",
            (30, True))
        assert all(r[2] > 30 for r in results)  # age column
    
    def test_query_zds_df(self):
        """Test DataFrame results."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")
        
        df = query_zds_df(self.tmp.name, "test",
            "SELECT name, age, score FROM data WHERE age < 30")
        
        assert isinstance(df, pd.DataFrame)
        assert "name" in df.columns
        assert "age" in df.columns
        assert all(df["age"] < 30)
    
    def test_register_zds(self):
        """Test registering as DuckDB view."""
        conn = duckdb.connect()
        register_zds(conn, self.tmp.name, "test", view_name="users")
        
        result = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        assert result[0] == 100
        
        conn.close()
    
    def test_export_query_to_zds(self):
        """Test exporting query results to new collection."""
        conn = duckdb.connect()
        
        # Create source table
        conn.execute("""
            CREATE TABLE source AS 
            SELECT * FROM (
                VALUES 
                    (1, 'Alice', 30),
                    (2, 'Bob', 25),
                    (3, 'Charlie', 35)
            ) AS t(id, name, age)
        """)
        
        # Export to ZDS
        count = export_query_to_zds(
            conn,
            "SELECT * FROM source WHERE age >= 30",
            self.tmp.name,
            collection="exported",
            id_column="id"
        )
        
        assert count == 2
        
        # Verify
        store = ZDSStore.open(self.tmp.name, collection="exported")
        assert len(store) == 2
        
        conn.close()
    
    def test_zds_connection(self):
        """Test ZDSConnection wrapper."""
        # Create second collection
        store2 = ZDSStore.open(self.tmp.name, collection="products")
        for i in range(10):
            store2.put(f"prod_{i}", {
                "name": f"Product {i}",
                "price": 10 + i * 5
            })
        
        with ZDSConnection(self.tmp.name) as zds:
            zds.register("test", view_name="users")
            zds.register("products")
            
            # Cross-collection query
            results = zds.query("""
                SELECT COUNT(*) as user_count FROM users
                UNION ALL
                SELECT COUNT(*) as product_count FROM products
            """)
            assert len(results) == 2
            
            # Export to new collection
            count = zds.export(
                "SELECT _id, name FROM users LIMIT 5",
                collection="sample"
            )
            assert count == 5
    
    def test_window_function(self):
        """Test window functions."""
        results = query_zds(self.tmp.name, "test", """
            SELECT 
                name,
                age,
                ROW_NUMBER() OVER (ORDER BY age DESC) as rank
            FROM data
            LIMIT 5
        """)
        assert len(results) == 5
        # Ranks should be 1-5
        ranks = [r[2] for r in results]
        assert ranks == [1, 2, 3, 4, 5]
    
    def test_json_handling(self):
        """Test JSON column handling."""
        # Add doc with nested data
        self.store.put("nested", {
            "id": 999,
            "name": "Nested",
            "age": 99,
            "score": 99.9,
            "active": True,
            "tags": ["a", "b", "c"],
            "metadata": {"key": "value"}
        })
        
        results = sql(self.tmp.name, "test",
            "SELECT * FROM data WHERE id = 999")
        assert len(results) == 1
