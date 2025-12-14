#!/usr/bin/env python3
"""
ZDS Benchmark Suite - Unified I/O Performance Comparison

Compares ZDS against comparable disk-backed storage solutions:
- ZDS Native Rust (JSONL + binary index)
- SQLite (via sqlite3)
- Pandas CSV
- Pandas JSONL  
- HuggingFace Datasets (Arrow format)

Methodology:
- Cold: Fresh process/file open, includes all initialization
- Warm: Data structure already loaded, measures operation only
- All tests use identical data and access patterns
"""

import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

# Optional dependencies
PANDAS_AVAILABLE = False
HF_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None

try:
    from datasets import Dataset as HFDataset
    HF_AVAILABLE = True
except ImportError:
    HFDataset = None

# ZDS imports
from zippy import FastZDSStore

NATIVE_AVAILABLE = False
try:
    import _zippy_data as native
    NATIVE_AVAILABLE = True
except ImportError:
    native = None


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class BenchmarkResult:
    """Single benchmark measurement."""
    approach: str           # e.g., "ZDS Native", "SQLite", "Pandas CSV"
    workload: str           # e.g., "write", "read_all", "random_access"
    mode: str               # "cold" or "warm"
    records: int
    time_ms: float
    throughput: float       # records/second
    details: Dict[str, float] = field(default_factory=dict)  # breakdown timings
    size_mb: Optional[float] = None


def format_throughput(t: float) -> str:
    """Format throughput with K/M suffix."""
    if t >= 1_000_000:
        return f"{t/1_000_000:.2f}M"
    elif t >= 1_000:
        return f"{t/1_000:.0f}k"
    else:
        return f"{t:.0f}"


# =============================================================================
# Test Data Generation
# =============================================================================

def generate_test_data(n_records: int, seed: int = 42) -> List[dict]:
    """Generate deterministic test records."""
    random.seed(seed)
    data = []
    for i in range(n_records):
        data.append({
            "id": f"record_{i:08d}",
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "age": random.randint(18, 80),
            "score": round(random.uniform(0, 100), 2),
            "active": random.choice([True, False]),
            "tags": random.sample(["a", "b", "c", "d", "e"], random.randint(1, 3)),
            "metadata": {
                "created": f"2025-01-{(i % 28) + 1:02d}",
                "source": random.choice(["web", "mobile", "api"])
            }
        })
    return data


def get_random_ids(data: List[dict], count: int, seed: int = 123) -> List[str]:
    """Get deterministic random sample of IDs."""
    random.seed(seed)
    return [d["id"] for d in random.sample(data, min(count, len(data)))]


def get_dir_size(path: str) -> float:
    """Get directory size in MB."""
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            total += os.path.getsize(os.path.join(dirpath, f))
    return total / (1024 * 1024)


def get_file_size(path: str) -> float:
    """Get file size in MB."""
    return os.path.getsize(path) / (1024 * 1024) if os.path.exists(path) else 0


# =============================================================================
# ZDS Native Rust Benchmarks
# =============================================================================

class ZDSNativeBenchmark:
    """ZDS Native Rust store benchmarks."""
    
    @staticmethod
    def write(data: List[dict], path: str) -> Tuple[float, Dict[str, float]]:
        """Write all records. Returns (total_ms, {detail: ms})."""
        details = {}
        
        start = time.perf_counter()
        store = native.NativeStore.open(path, "benchmark", len(data) + 1000)
        details["open_ms"] = (time.perf_counter() - start) * 1000
        
        # Use bulk write for speed
        try:
            import orjson
            doc_ids = [r["id"] for r in data]
            lines = [orjson.dumps(r) for r in data]
            jsonl_blob = b'\n'.join(lines)
            
            start = time.perf_counter()
            store.write_jsonl(jsonl_blob, doc_ids)
            details["write_ms"] = (time.perf_counter() - start) * 1000
        except ImportError:
            start = time.perf_counter()
            batch = [(r["id"], r) for r in data]
            store.put_batch(batch)
            details["write_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        store.flush()
        details["flush_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return total, details
    
    @staticmethod
    def read_all_cold(path: str) -> Tuple[int, float, Dict[str, float]]:
        """Cold read: open store + scan. Returns (count, total_ms, details)."""
        details = {}
        
        start = time.perf_counter()
        store = native.NativeStore.open(path, "benchmark", 1000)
        details["open_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        docs = store.scan()
        details["scan_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return len(docs), total, details
    
    @staticmethod
    def read_all_warm(store) -> Tuple[int, float, Dict[str, float]]:
        """Warm read: scan only. Returns (count, total_ms, details)."""
        details = {}
        
        start = time.perf_counter()
        docs = store.scan()
        details["scan_ms"] = (time.perf_counter() - start) * 1000
        
        return len(docs), details["scan_ms"], details
    
    @staticmethod
    def random_cold(path: str, ids: List[str]) -> Tuple[int, float, Dict[str, float]]:
        """Cold random access. Returns (count, total_ms, details)."""
        details = {}
        
        start = time.perf_counter()
        store = native.NativeStore.open(path, "benchmark", 1000)
        details["open_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        docs = [store.get(id) for id in ids]
        details["lookup_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return len([d for d in docs if d]), total, details
    
    @staticmethod
    def random_warm(store, ids: List[str]) -> Tuple[int, float, Dict[str, float]]:
        """Warm random access. Returns (count, total_ms, details)."""
        details = {}
        
        start = time.perf_counter()
        docs = [store.get(id) for id in ids]
        details["lookup_ms"] = (time.perf_counter() - start) * 1000
        
        return len([d for d in docs if d]), details["lookup_ms"], details


# =============================================================================
# SQLite Benchmarks
# =============================================================================

class SQLiteBenchmark:
    """SQLite benchmarks for comparison."""
    
    @staticmethod
    def write(data: List[dict], path: str) -> Tuple[float, Dict[str, float]]:
        """Write all records."""
        details = {}
        db_path = os.path.join(path, "data.db")
        os.makedirs(path, exist_ok=True)
        
        start = time.perf_counter()
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                data JSON NOT NULL
            )
        """)
        details["setup_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        conn.executemany(
            "INSERT INTO documents (id, data) VALUES (?, ?)",
            [(r["id"], json.dumps(r)) for r in data]
        )
        conn.commit()
        details["insert_ms"] = (time.perf_counter() - start) * 1000
        
        conn.close()
        total = sum(details.values())
        return total, details
    
    @staticmethod
    def read_all_cold(path: str) -> Tuple[int, float, Dict[str, float]]:
        """Cold read all."""
        details = {}
        db_path = os.path.join(path, "data.db")
        
        start = time.perf_counter()
        conn = sqlite3.connect(db_path)
        details["open_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        cursor = conn.execute("SELECT data FROM documents")
        docs = [json.loads(row[0]) for row in cursor]
        details["query_ms"] = (time.perf_counter() - start) * 1000
        
        conn.close()
        total = sum(details.values())
        return len(docs), total, details
    
    @staticmethod
    def read_all_warm(conn) -> Tuple[int, float, Dict[str, float]]:
        """Warm read all."""
        details = {}
        
        start = time.perf_counter()
        cursor = conn.execute("SELECT data FROM documents")
        docs = [json.loads(row[0]) for row in cursor]
        details["query_ms"] = (time.perf_counter() - start) * 1000
        
        return len(docs), details["query_ms"], details
    
    @staticmethod
    def random_cold(path: str, ids: List[str]) -> Tuple[int, float, Dict[str, float]]:
        """Cold random access."""
        details = {}
        db_path = os.path.join(path, "data.db")
        
        start = time.perf_counter()
        conn = sqlite3.connect(db_path)
        details["open_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        docs = []
        for id in ids:
            cursor = conn.execute("SELECT data FROM documents WHERE id = ?", (id,))
            row = cursor.fetchone()
            if row:
                docs.append(json.loads(row[0]))
        details["lookup_ms"] = (time.perf_counter() - start) * 1000
        
        conn.close()
        total = sum(details.values())
        return len(docs), total, details
    
    @staticmethod
    def random_warm(conn, ids: List[str]) -> Tuple[int, float, Dict[str, float]]:
        """Warm random access."""
        details = {}
        
        start = time.perf_counter()
        docs = []
        for id in ids:
            cursor = conn.execute("SELECT data FROM documents WHERE id = ?", (id,))
            row = cursor.fetchone()
            if row:
                docs.append(json.loads(row[0]))
        details["lookup_ms"] = (time.perf_counter() - start) * 1000
        
        return len(docs), details["lookup_ms"], details


# =============================================================================
# Pandas CSV Benchmarks
# =============================================================================

class PandasCSVBenchmark:
    """Pandas CSV benchmarks."""
    
    @staticmethod
    def write(data: List[dict], path: str) -> Tuple[float, Dict[str, float]]:
        """Write to CSV."""
        details = {}
        
        start = time.perf_counter()
        df = pd.DataFrame(data)
        df['tags'] = df['tags'].apply(json.dumps)
        df['metadata'] = df['metadata'].apply(json.dumps)
        details["convert_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        df.to_csv(path, index=False)
        details["write_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return total, details
    
    @staticmethod
    def read_all_cold(path: str) -> Tuple[int, float, Dict[str, float]]:
        """Cold read CSV."""
        details = {}
        
        start = time.perf_counter()
        df = pd.read_csv(path)
        details["read_ms"] = (time.perf_counter() - start) * 1000
        
        return len(df), details["read_ms"], details
    
    @staticmethod
    def read_all_warm(df) -> Tuple[int, float, Dict[str, float]]:
        """Warm read - DataFrame already in memory."""
        details = {}
        
        start = time.perf_counter()
        _ = df.copy()  # Simulate access
        details["copy_ms"] = (time.perf_counter() - start) * 1000
        
        return len(df), details["copy_ms"], details
    
    @staticmethod
    def random_cold(path: str, ids: List[str]) -> Tuple[int, float, Dict[str, float]]:
        """Cold random access - must load entire file."""
        details = {}
        
        start = time.perf_counter()
        df = pd.read_csv(path)
        details["read_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        result = df[df['id'].isin(ids)]
        details["filter_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return len(result), total, details
    
    @staticmethod
    def random_warm(df, ids: List[str]) -> Tuple[int, float, Dict[str, float]]:
        """Warm random access."""
        details = {}
        
        start = time.perf_counter()
        result = df[df['id'].isin(ids)]
        details["filter_ms"] = (time.perf_counter() - start) * 1000
        
        return len(result), details["filter_ms"], details


# =============================================================================
# HuggingFace Datasets Benchmarks
# =============================================================================

class HFDatasetsBenchmark:
    """HuggingFace Datasets benchmarks."""
    
    @staticmethod
    def write(data: List[dict], path: str) -> Tuple[float, Dict[str, float]]:
        """Write as Arrow dataset."""
        details = {}
        
        # Flatten nested structures for Arrow
        flat_data = []
        for r in data:
            flat_data.append({
                **{k: v for k, v in r.items() if k not in ['tags', 'metadata']},
                'tags': json.dumps(r['tags']),
                'metadata': json.dumps(r['metadata'])
            })
        
        start = time.perf_counter()
        ds = HFDataset.from_list(flat_data)
        details["create_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        ds.save_to_disk(path)
        details["save_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return total, details
    
    @staticmethod
    def read_all_cold(path: str) -> Tuple[int, float, Dict[str, float]]:
        """Cold read Arrow dataset."""
        details = {}
        
        start = time.perf_counter()
        ds = HFDataset.load_from_disk(path)
        details["load_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        _ = list(ds)  # Materialize
        details["iterate_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return len(ds), total, details
    
    @staticmethod
    def read_all_warm(ds) -> Tuple[int, float, Dict[str, float]]:
        """Warm read - dataset in memory."""
        details = {}
        
        start = time.perf_counter()
        _ = list(ds)
        details["iterate_ms"] = (time.perf_counter() - start) * 1000
        
        return len(ds), details["iterate_ms"], details
    
    @staticmethod
    def random_cold(path: str, indices: List[int]) -> Tuple[int, float, Dict[str, float]]:
        """Cold random access."""
        details = {}
        
        start = time.perf_counter()
        ds = HFDataset.load_from_disk(path)
        details["load_ms"] = (time.perf_counter() - start) * 1000
        
        start = time.perf_counter()
        docs = [ds[i] for i in indices]
        details["lookup_ms"] = (time.perf_counter() - start) * 1000
        
        total = sum(details.values())
        return len(docs), total, details
    
    @staticmethod
    def random_warm(ds, indices: List[int]) -> Tuple[int, float, Dict[str, float]]:
        """Warm random access."""
        details = {}
        
        start = time.perf_counter()
        docs = [ds[i] for i in indices]
        details["lookup_ms"] = (time.perf_counter() - start) * 1000
        
        return len(docs), details["lookup_ms"], details


# =============================================================================
# Benchmark Runner
# =============================================================================

def run_benchmarks(n_records: int = 100_000, n_random: int = 1000) -> List[BenchmarkResult]:
    """Run all benchmarks and return results."""
    results = []
    
    print(f"\n{'='*70}")
    print(f"ZDS Benchmark Suite - {n_records:,} records, {n_random} random lookups")
    print(f"{'='*70}\n")
    
    # Generate test data
    print("Generating test data...")
    data = generate_test_data(n_records)
    sample_ids = get_random_ids(data, n_random)
    sample_indices = list(range(0, n_records, n_records // n_random))[:n_random]
    
    with tempfile.TemporaryDirectory() as tmp:
        
        # =====================================================================
        # ZDS Native Rust
        # =====================================================================
        if NATIVE_AVAILABLE:
            print("\n[ZDS Native Rust]")
            zds_path = os.path.join(tmp, "zds_native")
            
            # Write
            total_ms, details = ZDSNativeBenchmark.write(data, zds_path)
            throughput = n_records / (total_ms / 1000)
            size = get_dir_size(zds_path)
            results.append(BenchmarkResult(
                approach="ZDS Native", workload="write", mode="cold",
                records=n_records, time_ms=total_ms, throughput=throughput,
                details=details, size_mb=size
            ))
            print(f"  write:       {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [open:{details.get('open_ms',0):.0f}, write:{details.get('write_ms',0):.0f}, flush:{details.get('flush_ms',0):.0f}]")
            
            # Read All Cold
            count, total_ms, details = ZDSNativeBenchmark.read_all_cold(zds_path)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="ZDS Native", workload="read_all", mode="cold",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [open:{details.get('open_ms',0):.0f}, scan:{details.get('scan_ms',0):.0f}] (cold)")
            
            # Read All Warm
            store = native.NativeStore.open(zds_path, "benchmark", 1000)
            count, total_ms, details = ZDSNativeBenchmark.read_all_warm(store)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="ZDS Native", workload="read_all", mode="warm",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [scan:{details.get('scan_ms',0):.0f}] (warm)")
            
            # Random Cold
            count, total_ms, details = ZDSNativeBenchmark.random_cold(zds_path, sample_ids)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="ZDS Native", workload="random", mode="cold",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [open:{details.get('open_ms',0):.0f}, lookup:{details.get('lookup_ms',0):.0f}] (cold)")
            
            # Random Warm
            store = native.NativeStore.open(zds_path, "benchmark", 1000)
            count, total_ms, details = ZDSNativeBenchmark.random_warm(store, sample_ids)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="ZDS Native", workload="random", mode="warm",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [lookup:{details.get('lookup_ms',0):.0f}] (warm)")
        
        # =====================================================================
        # SQLite
        # =====================================================================
        print("\n[SQLite]")
        sqlite_path = os.path.join(tmp, "sqlite")
        
        # Write
        total_ms, details = SQLiteBenchmark.write(data, sqlite_path)
        throughput = n_records / (total_ms / 1000)
        size = get_dir_size(sqlite_path)
        results.append(BenchmarkResult(
            approach="SQLite", workload="write", mode="cold",
            records=n_records, time_ms=total_ms, throughput=throughput,
            details=details, size_mb=size
        ))
        print(f"  write:       {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [setup:{details.get('setup_ms',0):.0f}, insert:{details.get('insert_ms',0):.0f}]")
        
        # Read All Cold
        count, total_ms, details = SQLiteBenchmark.read_all_cold(sqlite_path)
        throughput = count / (total_ms / 1000)
        results.append(BenchmarkResult(
            approach="SQLite", workload="read_all", mode="cold",
            records=count, time_ms=total_ms, throughput=throughput, details=details
        ))
        print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [open:{details.get('open_ms',0):.0f}, query:{details.get('query_ms',0):.0f}] (cold)")
        
        # Read All Warm
        conn = sqlite3.connect(os.path.join(sqlite_path, "data.db"))
        count, total_ms, details = SQLiteBenchmark.read_all_warm(conn)
        throughput = count / (total_ms / 1000)
        results.append(BenchmarkResult(
            approach="SQLite", workload="read_all", mode="warm",
            records=count, time_ms=total_ms, throughput=throughput, details=details
        ))
        print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [query:{details.get('query_ms',0):.0f}] (warm)")
        
        # Random Cold
        count, total_ms, details = SQLiteBenchmark.random_cold(sqlite_path, sample_ids)
        throughput = count / (total_ms / 1000)
        results.append(BenchmarkResult(
            approach="SQLite", workload="random", mode="cold",
            records=count, time_ms=total_ms, throughput=throughput, details=details
        ))
        print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [open:{details.get('open_ms',0):.0f}, lookup:{details.get('lookup_ms',0):.0f}] (cold)")
        
        # Random Warm
        conn = sqlite3.connect(os.path.join(sqlite_path, "data.db"))
        count, total_ms, details = SQLiteBenchmark.random_warm(conn, sample_ids)
        throughput = count / (total_ms / 1000)
        results.append(BenchmarkResult(
            approach="SQLite", workload="random", mode="warm",
            records=count, time_ms=total_ms, throughput=throughput, details=details
        ))
        print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [lookup:{details.get('lookup_ms',0):.0f}] (warm)")
        conn.close()
        
        # =====================================================================
        # Pandas CSV
        # =====================================================================
        if PANDAS_AVAILABLE:
            print("\n[Pandas CSV]")
            csv_path = os.path.join(tmp, "data.csv")
            
            # Write
            total_ms, details = PandasCSVBenchmark.write(data, csv_path)
            throughput = n_records / (total_ms / 1000)
            size = get_file_size(csv_path)
            results.append(BenchmarkResult(
                approach="Pandas CSV", workload="write", mode="cold",
                records=n_records, time_ms=total_ms, throughput=throughput,
                details=details, size_mb=size
            ))
            print(f"  write:       {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [convert:{details.get('convert_ms',0):.0f}, write:{details.get('write_ms',0):.0f}]")
            
            # Read All Cold
            count, total_ms, details = PandasCSVBenchmark.read_all_cold(csv_path)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="Pandas CSV", workload="read_all", mode="cold",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [read:{details.get('read_ms',0):.0f}] (cold)")
            
            # Read All Warm (DataFrame in memory)
            df = pd.read_csv(csv_path)
            count, total_ms, details = PandasCSVBenchmark.read_all_warm(df)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="Pandas CSV", workload="read_all", mode="warm",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [copy:{details.get('copy_ms',0):.0f}] (warm) *in-memory*")
            
            # Random Cold
            count, total_ms, details = PandasCSVBenchmark.random_cold(csv_path, sample_ids)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="Pandas CSV", workload="random", mode="cold",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [read:{details.get('read_ms',0):.0f}, filter:{details.get('filter_ms',0):.0f}] (cold)")
            
            # Random Warm
            df = pd.read_csv(csv_path)
            count, total_ms, details = PandasCSVBenchmark.random_warm(df, sample_ids)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="Pandas CSV", workload="random", mode="warm",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [filter:{details.get('filter_ms',0):.0f}] (warm)")
        
        # =====================================================================
        # HuggingFace Datasets
        # =====================================================================
        if HF_AVAILABLE:
            print("\n[HuggingFace Datasets]")
            hf_path = os.path.join(tmp, "hf_dataset")
            
            # Write
            total_ms, details = HFDatasetsBenchmark.write(data, hf_path)
            throughput = n_records / (total_ms / 1000)
            size = get_dir_size(hf_path)
            results.append(BenchmarkResult(
                approach="HF Datasets", workload="write", mode="cold",
                records=n_records, time_ms=total_ms, throughput=throughput,
                details=details, size_mb=size
            ))
            print(f"  write:       {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [create:{details.get('create_ms',0):.0f}, save:{details.get('save_ms',0):.0f}]")
            
            # Read All Cold
            count, total_ms, details = HFDatasetsBenchmark.read_all_cold(hf_path)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="HF Datasets", workload="read_all", mode="cold",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [load:{details.get('load_ms',0):.0f}, iterate:{details.get('iterate_ms',0):.0f}] (cold)")
            
            # Read All Warm
            ds = HFDataset.load_from_disk(hf_path)
            count, total_ms, details = HFDatasetsBenchmark.read_all_warm(ds)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="HF Datasets", workload="read_all", mode="warm",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  read_all:    {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [iterate:{details.get('iterate_ms',0):.0f}] (warm)")
            
            # Random Cold
            count, total_ms, details = HFDatasetsBenchmark.random_cold(hf_path, sample_indices)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="HF Datasets", workload="random", mode="cold",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [load:{details.get('load_ms',0):.0f}, lookup:{details.get('lookup_ms',0):.0f}] (cold)")
            
            # Random Warm
            ds = HFDataset.load_from_disk(hf_path)
            count, total_ms, details = HFDatasetsBenchmark.random_warm(ds, sample_indices)
            throughput = count / (total_ms / 1000)
            results.append(BenchmarkResult(
                approach="HF Datasets", workload="random", mode="warm",
                records=count, time_ms=total_ms, throughput=throughput, details=details
            ))
            print(f"  random:      {format_throughput(throughput):>8} rec/s  ({total_ms:.0f}ms) [lookup:{details.get('lookup_ms',0):.0f}] (warm)")
    
    return results


def print_summary_table(results: List[BenchmarkResult]):
    """Print a clean comparison table."""
    print(f"\n{'='*70}")
    print("SUMMARY TABLE")
    print(f"{'='*70}\n")
    
    # Group by workload
    workloads = ["write", "read_all", "random"]
    modes = ["cold", "warm"]
    
    for workload in workloads:
        print(f"\n### {workload.upper()}")
        print(f"| Approach | Cold | Warm |")
        print(f"|----------|------|------|")
        
        # Get unique approaches
        approaches = []
        for r in results:
            if r.approach not in approaches:
                approaches.append(r.approach)
        
        for approach in approaches:
            cold_r = next((r for r in results if r.approach == approach and r.workload == workload and r.mode == "cold"), None)
            warm_r = next((r for r in results if r.approach == approach and r.workload == workload and r.mode == "warm"), None)
            
            cold_str = f"{format_throughput(cold_r.throughput)} rec/s" if cold_r else "N/A"
            warm_str = f"{format_throughput(warm_r.throughput)} rec/s" if warm_r else "N/A"
            
            print(f"| {approach:<12} | {cold_str:<12} | {warm_str:<12} |")
    
    # Storage size comparison
    print(f"\n### STORAGE SIZE")
    print(f"| Approach | Size |")
    print(f"|----------|------|")
    seen = set()
    for r in results:
        if r.approach not in seen and r.size_mb:
            print(f"| {r.approach:<12} | {r.size_mb:.1f} MB |")
            seen.add(r.approach)


def print_markdown_table(results: List[BenchmarkResult]):
    """Print markdown table for README."""
    print(f"\n{'='*70}")
    print("MARKDOWN TABLE (for README)")
    print(f"{'='*70}\n")
    
    print("```")
    print("| Approach | Write | Read All (cold) | Read All (warm) | Random (cold) | Random (warm) |")
    print("|----------|-------|-----------------|-----------------|---------------|---------------|")
    
    approaches = []
    for r in results:
        if r.approach not in approaches:
            approaches.append(r.approach)
    
    for approach in approaches:
        row = [approach]
        for workload in ["write", "read_all", "read_all", "random", "random"]:
            mode = "cold" if workload == "write" or row.count(approach) in [1, 3] else "warm"
            if workload == "read_all":
                mode = "cold" if len(row) == 2 else "warm"
            if workload == "random":
                mode = "cold" if len(row) == 4 else "warm"
            
            r = next((x for x in results if x.approach == approach and x.workload == workload and x.mode == mode), None)
            if r:
                row.append(f"{format_throughput(r.throughput)} rec/s")
            else:
                row.append("N/A")
        
        print(f"| {row[0]:<12} | {row[1]:<13} | {row[2]:<15} | {row[3]:<15} | {row[4]:<13} | {row[5]:<13} |")
    print("```")


def main():
    """Run benchmarks."""
    import argparse
    parser = argparse.ArgumentParser(description="ZDS Benchmark Suite")
    parser.add_argument("-n", "--records", type=int, default=100_000,
                        help="Number of records (default: 100,000)")
    parser.add_argument("-r", "--random", type=int, default=1000,
                        help="Number of random lookups (default: 1000)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output JSON file for results")
    args = parser.parse_args()
    
    print("Available libraries:")
    print(f"  ZDS Native: {NATIVE_AVAILABLE}")
    print(f"  Pandas: {PANDAS_AVAILABLE}")
    print(f"  HuggingFace Datasets: {HF_AVAILABLE}")
    
    results = run_benchmarks(args.records, args.random)
    print_summary_table(results)
    print_markdown_table(results)
    
    if args.output:
        import json as json_module
        data = [
            {
                "approach": r.approach,
                "workload": r.workload,
                "mode": r.mode,
                "records": r.records,
                "time_ms": r.time_ms,
                "throughput": r.throughput,
                "details": r.details,
                "size_mb": r.size_mb
            }
            for r in results
        ]
        with open(args.output, 'w') as f:
            json_module.dump(data, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
