#!/usr/bin/env python3
"""DuckDB integration examples for ZDS.

Demonstrates SQL querying of ZDS data:
- Basic SQL queries
- Aggregations and analytics
- Window functions
- Cross-collection joins
- Export query results

Requires: pip install duckdb pandas

Output is saved to: examples/data/04_duckdb/
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

from zippy import ZDSStore

# Check DuckDB availability
try:
    import duckdb
    from zippy.duckdb_compat import (
        register_zds, query_zds, query_zds_df,
        export_query_to_zds, ZDSConnection,
        sql, aggregate, count_where
    )
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    print("Note: DuckDB not installed. Install with: pip install duckdb")

# Output directory
DATA_DIR = Path(__file__).parent.parent / "data" / "04_duckdb"


def setup_data_dir():
    """Create/clean the data directory."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return str(DATA_DIR)


def create_sample_data(data_path: str):
    """Create sample data for demos."""
    import random
    random.seed(42)
    
    regions = ["North", "South", "East", "West"]
    products = ["Widget", "Gadget", "Gizmo", "Doodad"]
    
    # Sales data
    store = ZDSStore.open(data_path, collection="sales")
    for i in range(500):
        store.put(f"sale_{i:05d}", {
            "region": random.choice(regions),
            "product": random.choice(products),
            "quantity": random.randint(1, 100),
            "unit_price": round(random.uniform(10, 100), 2),
            "date": f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        })
    
    # Customers
    store = ZDSStore.open(data_path, collection="customers")
    for i in range(100):
        store.put(f"cust_{i:04d}", {
            "name": f"Customer {i}",
            "region": random.choice(regions),
            "tier": random.choice(["bronze", "silver", "gold", "platinum"]),
            "total_orders": random.randint(1, 50),
            "active": random.choice([True, True, True, False])
        })
    
    print(f"Created sample data: 500 sales, 100 customers")


def example_basic_sql(data_path: str):
    """Basic SQL queries on ZDS data."""
    print("=" * 60)
    print("Example: Basic SQL Queries")
    print("=" * 60)
    
    # Count
    results = sql(data_path, "sales", "SELECT COUNT(*) as count FROM data")
    print(f"\nTotal sales records: {results[0][0]}")
    
    # WHERE clause
    results = sql(data_path, "sales", 
        "SELECT * FROM data WHERE quantity > 50 LIMIT 5")
    print(f"\nHigh quantity sales (>50): {len(results)} shown")
    
    # Aggregation
    results = aggregate(data_path, "sales", "region", 
        "SUM(quantity) as total_qty, AVG(unit_price) as avg_price")
    print(f"\nSales by region:")
    for row in results:
        print(f"  {row[0]}: qty={row[1]}, avg_price=${row[2]:.2f}")
    
    # Count with condition
    high_value = count_where(data_path, "sales", "unit_price > 75")
    print(f"\nHigh-value sales (>$75): {high_value}")


def example_joins_and_analytics(data_path: str):
    """Complex queries with joins."""
    print("\n" + "=" * 60)
    print("Example: Joins and Analytics")
    print("=" * 60)
    
    with ZDSConnection(data_path) as zds:
        zds.register("sales")
        zds.register("customers")
        
        # Regional analysis
        results = zds.query("""
            SELECT 
                region,
                COUNT(*) as sale_count,
                SUM(quantity * unit_price) as total_revenue
            FROM sales
            GROUP BY region
            ORDER BY total_revenue DESC
        """)
        
        print("\nRevenue by region:")
        for row in results:
            print(f"  {row[0]}: {row[1]} sales, ${row[2]:,.2f}")
        
        # Customer tiers
        results = zds.query("""
            SELECT tier, COUNT(*) as count, AVG(total_orders) as avg_orders
            FROM customers
            GROUP BY tier
            ORDER BY avg_orders DESC
        """)
        
        print("\nCustomer tiers:")
        for row in results:
            print(f"  {row[0]}: {row[1]} customers, {row[2]:.1f} avg orders")


def example_window_functions(data_path: str):
    """Window functions for analytics."""
    print("\n" + "=" * 60)
    print("Example: Window Functions")
    print("=" * 60)
    
    results = query_zds(data_path, "sales", """
        SELECT 
            _id,
            region,
            product,
            quantity,
            RANK() OVER (PARTITION BY region ORDER BY quantity DESC) as rank_in_region
        FROM data
        QUALIFY rank_in_region <= 3
        ORDER BY region, rank_in_region
        LIMIT 12
    """)
    
    print("\nTop 3 sales by quantity per region:")
    current_region = None
    for row in results:
        if row[1] != current_region:
            current_region = row[1]
            print(f"\n  {current_region}:")
        print(f"    #{row[4]}: {row[2]} - {row[3]} units")


def example_export_query(data_path: str):
    """Export query results to new collection."""
    print("\n" + "=" * 60)
    print("Example: Export Query Results")
    print("=" * 60)
    
    with ZDSConnection(data_path) as zds:
        zds.register("sales")
        
        # Export aggregated data
        count = zds.export(
            """
            SELECT 
                product || '_' || region as id,
                product,
                region,
                SUM(quantity) as total_qty,
                SUM(quantity * unit_price) as total_revenue
            FROM sales
            GROUP BY product, region
            """,
            collection="product_region_summary",
            id_column="id"
        )
        
        print(f"Exported {count} summary records to 'product_region_summary'")
    
    # Verify
    store = ZDSStore.open(data_path, collection="product_region_summary")
    print(f"New collection has {len(store)} documents")
    
    # Query the new collection
    results = sql(data_path, "product_region_summary",
        "SELECT * FROM data ORDER BY total_revenue DESC LIMIT 5")
    print("\nTop 5 product-region combinations by revenue:")
    for row in results:
        print(f"  {row}")


def example_dataframe_results(data_path: str):
    """Get query results as pandas DataFrame."""
    try:
        import pandas as pd
    except ImportError:
        print("\nSkipping DataFrame example - pandas not installed")
        return
    
    print("\n" + "=" * 60)
    print("Example: DataFrame Query Results")
    print("=" * 60)
    
    df = query_zds_df(data_path, "sales", """
        SELECT 
            product,
            region,
            SUM(quantity) as total_qty,
            SUM(quantity * unit_price) as revenue
        FROM data
        GROUP BY product, region
        ORDER BY revenue DESC
    """)
    
    print("\nSales summary (DataFrame):")
    print(df.head(10))
    
    # Pivot table
    pivot = df.pivot_table(
        index="product",
        columns="region",
        values="revenue",
        aggfunc="sum"
    ).fillna(0)
    
    print("\nRevenue pivot table:")
    print(pivot.round(2))


def main():
    """Run all DuckDB examples."""
    if not DUCKDB_AVAILABLE:
        print("DuckDB is required for these examples.")
        print("Install with: pip install duckdb")
        return
    
    data_path = setup_data_dir()
    print(f"Output directory: {data_path}\n")
    
    create_sample_data(data_path)
    example_basic_sql(data_path)
    example_joins_and_analytics(data_path)
    example_window_functions(data_path)
    example_export_query(data_path)
    example_dataframe_results(data_path)
    
    print("\n" + "=" * 60)
    print("All DuckDB examples completed!")
    print(f"Data saved to: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
