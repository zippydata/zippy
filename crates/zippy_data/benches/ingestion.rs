//! Benchmarks for data ingestion.

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use serde_json::json;
use tempfile::TempDir;
use zippy_data::{
    writer::{BufferedWriter, SyncWriter, WriteConfig},
    Layout,
};

fn bench_sync_write(c: &mut Criterion) {
    let mut group = c.benchmark_group("ingestion_sync");

    for count in [10, 100, 1000].iter() {
        group.throughput(Throughput::Elements(*count as u64));

        group.bench_with_input(BenchmarkId::new("sync_write", count), count, |b, &count| {
            b.iter_with_setup(
                || {
                    let tmp = TempDir::new().unwrap();
                    let root = tmp.path().to_path_buf();
                    Layout::init_root(&root).unwrap();
                    (tmp, root)
                },
                |(_tmp, root)| {
                    let mut writer = SyncWriter::new(&root, "bench").unwrap();
                    for i in 0..count {
                        let doc = json!({
                            "id": i,
                            "name": format!("user_{}", i),
                        });
                        writer.put(&format!("doc{:06}", i), &doc).unwrap();
                    }
                    black_box(())
                },
            );
        });
    }

    group.finish();
}

fn bench_buffered_write(c: &mut Criterion) {
    let mut group = c.benchmark_group("ingestion_buffered");

    for count in [100, 1000, 10000].iter() {
        group.throughput(Throughput::Elements(*count as u64));

        group.bench_with_input(
            BenchmarkId::new("buffered_write", count),
            count,
            |b, &count| {
                b.iter_with_setup(
                    || {
                        let tmp = TempDir::new().unwrap();
                        let root = tmp.path().to_path_buf();
                        Layout::init_root(&root).unwrap();
                        (tmp, root)
                    },
                    |(_tmp, root)| {
                        let config = WriteConfig {
                            max_pending_ops: 10000,
                            max_pending_bytes: 100 * 1024 * 1024,
                            flush_interval_ms: 60000,
                        };
                        let mut writer = BufferedWriter::new(&root, "bench", config).unwrap();
                        for i in 0..count {
                            let doc = json!({
                                "id": i,
                                "name": format!("user_{}", i),
                            });
                            writer.put(format!("doc{:06}", i), doc).unwrap();
                        }
                        writer.flush().unwrap();
                        black_box(())
                    },
                );
            },
        );
    }

    group.finish();
}

fn bench_different_batch_sizes(c: &mut Criterion) {
    let mut group = c.benchmark_group("ingestion_batch_size");
    let doc_count = 10000;

    for batch_size in [100, 500, 1000, 5000].iter() {
        group.throughput(Throughput::Elements(doc_count as u64));

        group.bench_with_input(
            BenchmarkId::new("batch_size", batch_size),
            batch_size,
            |b, &batch_size| {
                b.iter_with_setup(
                    || {
                        let tmp = TempDir::new().unwrap();
                        let root = tmp.path().to_path_buf();
                        Layout::init_root(&root).unwrap();
                        (tmp, root)
                    },
                    |(_tmp, root)| {
                        let config = WriteConfig {
                            max_pending_ops: batch_size,
                            max_pending_bytes: 100 * 1024 * 1024,
                            flush_interval_ms: 60000,
                        };
                        let mut writer = BufferedWriter::new(&root, "bench", config).unwrap();
                        for i in 0..doc_count {
                            let doc = json!({
                                "id": i,
                                "name": format!("user_{}", i),
                            });
                            writer.put(format!("doc{:06}", i), doc).unwrap();
                        }
                        writer.flush().unwrap();
                        black_box(())
                    },
                );
            },
        );
    }

    group.finish();
}

criterion_group!(
    benches,
    bench_sync_write,
    bench_buffered_write,
    bench_different_batch_sizes
);
criterion_main!(benches);
