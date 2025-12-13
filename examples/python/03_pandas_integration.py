#!/usr/bin/env python3
"""Pandas integration examples.

Demonstrates ZDS integration with pandas:
- DataFrame to ZDS conversion
- ZDS to DataFrame loading
- Query and aggregation
- Large dataset handling

Requires: pip install pandas

Output is saved to: examples/data/03_pandas/
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

from zippy import ZDSStore, ZDataset
from zippy.pandas_compat import read_zds, to_zds

# Check pandas availability
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Note: pandas not installed. Install with: pip install pandas")

# Output directory
DATA_DIR = Path(__file__).parent.parent / "data" / "03_pandas"


def setup_data_dir():
    """Create/clean the data directory."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return str(DATA_DIR)


def example_dataframe_roundtrip(data_path: str):
    """Convert between DataFrame and ZDS."""
    if not PANDAS_AVAILABLE:
        print("Skipping - pandas not installed")
        return
    
    print("=" * 60)
    print("Example: DataFrame <-> ZDS Roundtrip")
    print("=" * 60)
    
    # Create a DataFrame
    df = pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "age": [28, 35, 42, 31, 29],
        "salary": [75000, 85000, 95000, 72000, 68000],
        "department": ["Engineering", "Sales", "Engineering", "Marketing", "Engineering"]
    })
    
    print("Original DataFrame:")
    print(df)
    print(f"\nShape: {df.shape}")
    
    # Save to ZDS
    to_zds(df, data_path, collection="employees", doc_id_column="name")
    print(f"\nSaved to ZDS at {data_path}/collections/employees/")
    
    # Reload from ZDS
    df_loaded = read_zds(data_path, collection="employees")
    print("\nLoaded DataFrame:")
    print(df_loaded)


def example_large_dataframe(data_path: str):
    """Handle larger DataFrames."""
    if not PANDAS_AVAILABLE:
        return
    
    print("\n" + "=" * 60)
    print("Example: Large DataFrame Handling")
    print("=" * 60)
    
    import random
    import time
    
    n_rows = 10000
    print(f"Creating DataFrame with {n_rows} rows...")
    
    random.seed(42)
    df = pd.DataFrame({
        "id": [f"record_{i:06d}" for i in range(n_rows)],
        "value_a": [random.gauss(100, 15) for _ in range(n_rows)],
        "value_b": [random.gauss(50, 10) for _ in range(n_rows)],
        "category": [random.choice(["A", "B", "C", "D"]) for _ in range(n_rows)],
        "flag": [random.choice([True, False]) for _ in range(n_rows)]
    })
    
    print(f"DataFrame memory: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
    
    # Save to ZDS
    start = time.time()
    to_zds(df, data_path, collection="large_data", doc_id_column="id")
    save_time = time.time() - start
    print(f"Saved to ZDS in {save_time:.2f}s")
    
    # Load back
    start = time.time()
    df_loaded = read_zds(data_path, collection="large_data")
    load_time = time.time() - start
    print(f"Loaded from ZDS in {load_time:.2f}s, shape: {df_loaded.shape}")


def example_sales_analysis(data_path: str):
    """Query and aggregate sales data."""
    if not PANDAS_AVAILABLE:
        return
    
    print("\n" + "=" * 60)
    print("Example: Sales Data Analysis")
    print("=" * 60)
    
    import random
    random.seed(42)
    
    products = ["Widget", "Gadget", "Gizmo", "Doohickey"]
    regions = ["North", "South", "East", "West"]
    
    data = []
    for i in range(1000):
        data.append({
            "sale_id": f"sale_{i:05d}",
            "product": random.choice(products),
            "region": random.choice(regions),
            "quantity": random.randint(1, 100),
            "unit_price": round(random.uniform(10, 100), 2),
            "date": f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        })
    
    df = pd.DataFrame(data)
    to_zds(df, data_path, collection="sales", doc_id_column="sale_id")
    print(f"Created sales data: {len(df)} records")
    
    # Reload and analyze
    df_sales = read_zds(data_path, collection="sales")
    df_sales["total"] = df_sales["quantity"] * df_sales["unit_price"]
    
    print(f"\nTotal revenue: ${df_sales['total'].sum():,.2f}")
    
    # Group by product
    by_product = df_sales.groupby("product").agg({
        "quantity": "sum",
        "total": "sum"
    }).round(2)
    print(f"\nBy Product:\n{by_product}")
    
    # Group by region
    by_region = df_sales.groupby("region")["total"].sum().round(2)
    print(f"\nBy Region:\n{by_region}")
    
    print(f"\nData saved to: {data_path}/collections/sales/")


def main():
    """Run all pandas examples."""
    if not PANDAS_AVAILABLE:
        print("pandas is required for these examples.")
        print("Install with: pip install pandas")
        return
    
    data_path = setup_data_dir()
    print(f"Output directory: {data_path}\n")
    
    example_dataframe_roundtrip(data_path)
    example_large_dataframe(data_path)
    example_sales_analysis(data_path)
    
    print("\n" + "=" * 60)
    print("All pandas examples completed!")
    print(f"Data saved to: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
