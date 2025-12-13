#!/usr/bin/env python3
"""
Benchmark: ML Training Simulation

Compares dataset iteration performance for ML workloads:
- Sequential iteration
- Shuffled iteration  
- Batched iteration
- Multi-epoch training simulation

Tests ZDS against HuggingFace Datasets and PyTorch DataLoader patterns.
"""

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

# Try importing optional dependencies
TORCH_AVAILABLE = False
HF_AVAILABLE = False

try:
    import torch
    from torch.utils.data import Dataset as TorchDataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    pass

try:
    from datasets import Dataset as HFDataset
    HF_AVAILABLE = True
except ImportError:
    pass

from zippy import ZDSStore, ZDataset, ZIterableDataset


@dataclass
class BenchmarkResult:
    """Benchmark result."""
    name: str
    operation: str
    samples: int
    time_seconds: float
    samples_per_second: float
    batches: Optional[int] = None
    epochs: Optional[int] = None

    def __str__(self):
        extras = []
        if self.batches:
            extras.append(f"{self.batches} batches")
        if self.epochs:
            extras.append(f"{self.epochs} epochs")
        extra_str = f" ({', '.join(extras)})" if extras else ""
        return f"{self.name} - {self.operation}: {self.time_seconds:.3f}s, {self.samples_per_second:.0f} samples/s{extra_str}"


def generate_ml_data(n_samples: int) -> List[dict]:
    """Generate ML training data."""
    import random
    random.seed(42)
    
    data = []
    for i in range(n_samples):
        data.append({
            "id": f"sample_{i:08d}",
            "features": [random.gauss(0, 1) for _ in range(128)],  # 128-dim features
            "label": random.randint(0, 9),
            "weight": round(random.uniform(0.5, 1.5), 3)
        })
    return data


class ZDSMLBenchmark:
    """ZDS benchmarks for ML workloads."""
    
    @staticmethod
    def setup(data: List[dict], path: str) -> str:
        store = ZDSStore.open(path, collection="ml_data")
        for record in data:
            store.put(record["id"], record)
        return path
    
    @staticmethod
    def sequential_iteration(path: str) -> int:
        store = ZDSStore.open(path, collection="ml_data")
        dataset = ZDataset(store)
        count = 0
        for _ in dataset:
            count += 1
        return count
    
    @staticmethod
    def shuffled_iteration(path: str, seed: int = 42) -> int:
        store = ZDSStore.open(path, collection="ml_data")
        dataset = ZDataset(store).shuffle(seed=seed)
        count = 0
        for _ in dataset:
            count += 1
        return count
    
    @staticmethod
    def batched_iteration(path: str, batch_size: int = 32) -> tuple:
        store = ZDSStore.open(path, collection="ml_data")
        dataset = ZDataset(store)
        batches = 0
        samples = 0
        for batch in dataset.batch(batch_size):
            batches += 1
            samples += len(batch)
        return samples, batches
    
    @staticmethod
    def streaming_shuffle(path: str, buffer_size: int = 1000, seed: int = 42) -> int:
        store = ZDSStore.open(path, collection="ml_data")
        dataset = ZIterableDataset(store).shuffle(buffer_size=buffer_size, seed=seed)
        count = 0
        for _ in dataset:
            count += 1
        return count
    
    @staticmethod
    def multi_epoch_training(path: str, epochs: int = 3, batch_size: int = 32) -> tuple:
        store = ZDSStore.open(path, collection="ml_data")
        dataset = ZDataset(store)
        
        total_batches = 0
        total_samples = 0
        
        for epoch in range(epochs):
            shuffled = dataset.shuffle(seed=epoch)
            for batch in shuffled.batch(batch_size):
                total_batches += 1
                total_samples += len(batch)
                
                # Simulate minimal processing
                _ = [item["features"] for item in batch]
        
        return total_samples, total_batches


class HFMLBenchmark:
    """HuggingFace Datasets benchmarks for ML."""
    
    @staticmethod
    def setup(data: List[dict], path: str) -> str:
        flat_data = []
        for d in data:
            flat = {**d}
            flat['features'] = json.dumps(d['features'])  # Serialize list
            flat_data.append(flat)
        ds = HFDataset.from_list(flat_data)
        ds.save_to_disk(path)
        return path
    
    @staticmethod
    def sequential_iteration(path: str) -> int:
        ds = HFDataset.load_from_disk(path)
        count = 0
        for _ in ds:
            count += 1
        return count
    
    @staticmethod
    def shuffled_iteration(path: str, seed: int = 42) -> int:
        ds = HFDataset.load_from_disk(path)
        ds = ds.shuffle(seed=seed)
        count = 0
        for _ in ds:
            count += 1
        return count
    
    @staticmethod
    def batched_iteration(path: str, batch_size: int = 32) -> tuple:
        ds = HFDataset.load_from_disk(path)
        batches = 0
        samples = 0
        for i in range(0, len(ds), batch_size):
            batch = ds[i:i+batch_size]
            batches += 1
            samples += len(batch['id'])  # Count via any column
        return samples, batches
    
    @staticmethod
    def multi_epoch_training(path: str, epochs: int = 3, batch_size: int = 32) -> tuple:
        ds = HFDataset.load_from_disk(path)
        
        total_batches = 0
        total_samples = 0
        
        for epoch in range(epochs):
            shuffled = ds.shuffle(seed=epoch)
            for i in range(0, len(shuffled), batch_size):
                batch = shuffled[i:i+batch_size]
                total_batches += 1
                total_samples += len(batch['id'])
                
                # Simulate minimal processing (features are serialized)
                _ = batch['features']
        
        return total_samples, total_batches


def run_benchmarks(n_samples: int = 10000) -> List[BenchmarkResult]:
    """Run ML benchmarks."""
    print(f"\n{'='*60}")
    print(f"ML Training Benchmarks: {n_samples:,} samples")
    print(f"{'='*60}\n")
    
    results = []
    data = generate_ml_data(n_samples)
    
    with tempfile.TemporaryDirectory() as tmp:
        # Setup ZDS
        print("Setting up ZDS...")
        zds_path = os.path.join(tmp, "zds_ml")
        ZDSMLBenchmark.setup(data, zds_path)
        
        # Setup HF if available
        hf_path = None
        if HF_AVAILABLE:
            print("Setting up HuggingFace Datasets...")
            hf_path = os.path.join(tmp, "hf_ml")
            HFMLBenchmark.setup(data, hf_path)
        
        # =====================
        # Sequential Iteration
        # =====================
        print("\n--- Sequential Iteration ---")
        
        start = time.perf_counter()
        count = ZDSMLBenchmark.sequential_iteration(zds_path)
        elapsed = time.perf_counter() - start
        result = BenchmarkResult("ZDS", "sequential", count, elapsed, count/elapsed)
        results.append(result)
        print(f"  {result}")
        
        if HF_AVAILABLE:
            start = time.perf_counter()
            count = HFMLBenchmark.sequential_iteration(hf_path)
            elapsed = time.perf_counter() - start
            result = BenchmarkResult("HF Datasets", "sequential", count, elapsed, count/elapsed)
            results.append(result)
            print(f"  {result}")
        
        # =====================
        # Shuffled Iteration
        # =====================
        print("\n--- Shuffled Iteration ---")
        
        start = time.perf_counter()
        count = ZDSMLBenchmark.shuffled_iteration(zds_path)
        elapsed = time.perf_counter() - start
        result = BenchmarkResult("ZDS", "shuffled", count, elapsed, count/elapsed)
        results.append(result)
        print(f"  {result}")
        
        if HF_AVAILABLE:
            start = time.perf_counter()
            count = HFMLBenchmark.shuffled_iteration(hf_path)
            elapsed = time.perf_counter() - start
            result = BenchmarkResult("HF Datasets", "shuffled", count, elapsed, count/elapsed)
            results.append(result)
            print(f"  {result}")
        
        # =====================
        # Batched Iteration
        # =====================
        print("\n--- Batched Iteration (batch_size=32) ---")
        
        start = time.perf_counter()
        samples, batches = ZDSMLBenchmark.batched_iteration(zds_path, 32)
        elapsed = time.perf_counter() - start
        result = BenchmarkResult("ZDS", "batched", samples, elapsed, samples/elapsed, batches=batches)
        results.append(result)
        print(f"  {result}")
        
        if HF_AVAILABLE:
            start = time.perf_counter()
            samples, batches = HFMLBenchmark.batched_iteration(hf_path, 32)
            elapsed = time.perf_counter() - start
            result = BenchmarkResult("HF Datasets", "batched", samples, elapsed, samples/elapsed, batches=batches)
            results.append(result)
            print(f"  {result}")
        
        # =====================
        # Streaming with Shuffle Buffer
        # =====================
        print("\n--- Streaming Shuffle (buffer=1000) ---")
        
        start = time.perf_counter()
        count = ZDSMLBenchmark.streaming_shuffle(zds_path, buffer_size=1000)
        elapsed = time.perf_counter() - start
        result = BenchmarkResult("ZDS Iterable", "streaming_shuffle", count, elapsed, count/elapsed)
        results.append(result)
        print(f"  {result}")
        
        # =====================
        # Multi-Epoch Training Simulation
        # =====================
        print("\n--- Multi-Epoch Training (3 epochs, batch=32) ---")
        
        start = time.perf_counter()
        samples, batches = ZDSMLBenchmark.multi_epoch_training(zds_path, epochs=3, batch_size=32)
        elapsed = time.perf_counter() - start
        result = BenchmarkResult("ZDS", "training_sim", samples, elapsed, samples/elapsed, batches=batches, epochs=3)
        results.append(result)
        print(f"  {result}")
        
        if HF_AVAILABLE:
            start = time.perf_counter()
            samples, batches = HFMLBenchmark.multi_epoch_training(hf_path, epochs=3, batch_size=32)
            elapsed = time.perf_counter() - start
            result = BenchmarkResult("HF Datasets", "training_sim", samples, elapsed, samples/elapsed, batches=batches, epochs=3)
            results.append(result)
            print(f"  {result}")
    
    return results


def print_summary(results: List[BenchmarkResult]):
    """Print benchmark summary."""
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}\n")
    
    from collections import defaultdict
    by_op = defaultdict(list)
    for r in results:
        by_op[r.operation].append(r)
    
    for op, items in sorted(by_op.items()):
        print(f"\n{op.upper()}")
        print("-" * 50)
        items_sorted = sorted(items, key=lambda x: -x.samples_per_second)
        for r in items_sorted:
            print(f"  {r.name:15} {r.samples_per_second:>12,.0f} samples/s  {r.time_seconds:.3f}s")


def main():
    """Run ML benchmarks."""
    import argparse
    parser = argparse.ArgumentParser(description="ZDS ML Training Benchmarks")
    parser.add_argument("-n", "--samples", type=int, default=10000,
                        help="Number of samples (default: 10000)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output JSON file for results")
    args = parser.parse_args()
    
    print("Available libraries:")
    print(f"  PyTorch: {TORCH_AVAILABLE}")
    print(f"  HuggingFace Datasets: {HF_AVAILABLE}")
    
    results = run_benchmarks(args.samples)
    print_summary(results)
    
    if args.output:
        data = [
            {
                "name": r.name,
                "operation": r.operation,
                "samples": r.samples,
                "time_seconds": r.time_seconds,
                "samples_per_second": r.samples_per_second,
                "batches": r.batches,
                "epochs": r.epochs
            }
            for r in results
        ]
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
