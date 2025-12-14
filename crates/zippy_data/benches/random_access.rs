//! Benchmarks for random access operations.

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use serde_json::json;
use tempfile::TempDir;
use zippy_data::{writer::BufferedWriter, Engine, Layout, WriteConfig};

fn setup_benchmark_data(doc_count: usize) -> (TempDir, std::path::PathBuf) {
    let tmp = TempDir::new().unwrap();
    let root = tmp.path().to_path_buf();
    Layout::init_root(&root).unwrap();

    let config = WriteConfig {
        max_pending_ops: 10000,
        max_pending_bytes: 100 * 1024 * 1024,
        flush_interval_ms: 60000,
    };

    let mut writer = BufferedWriter::new(&root, "bench", config).unwrap();

    for i in 0..doc_count {
        let doc = json!({
            "id": i,
            "name": format!("user_{}", i),
            "data": "x".repeat(100),
        });
        writer.put(format!("doc{:06}", i), doc).unwrap();
    }
    writer.flush().unwrap();

    (tmp, root)
}

fn bench_get_by_id(c: &mut Criterion) {
    let mut group = c.benchmark_group("random_access");

    for count in [1000, 10000].iter() {
        let (_tmp, root) = setup_benchmark_data(*count);

        group.bench_with_input(BenchmarkId::new("get_by_id", count), count, |b, count| {
            let engine = Engine::open(&root, "bench").unwrap();
            let mid = count / 2;
            let doc_id = format!("doc{:06}", mid);
            b.iter(|| {
                let doc = engine.get_document(&doc_id).unwrap();
                black_box(doc)
            });
        });
    }

    group.finish();
}

fn bench_get_by_index(c: &mut Criterion) {
    let mut group = c.benchmark_group("random_access");

    for count in [1000, 10000].iter() {
        let (_tmp, root) = setup_benchmark_data(*count);

        group.bench_with_input(
            BenchmarkId::new("get_by_index", count),
            count,
            |b, count| {
                let engine = Engine::open(&root, "bench").unwrap();
                let mid = count / 2;
                b.iter(|| {
                    let doc = engine.get_document_at(mid).unwrap();
                    black_box(doc)
                });
            },
        );
    }

    group.finish();
}

fn bench_random_batch(c: &mut Criterion) {
    let (_tmp, root) = setup_benchmark_data(10000);
    let engine = Engine::open(&root, "bench").unwrap();

    let mut group = c.benchmark_group("random_batch");

    group.bench_function("100_random_gets", |b| {
        let indices: Vec<usize> = (0..100).map(|i| (i * 97) % 10000).collect();
        b.iter(|| {
            for &idx in &indices {
                let doc = engine.get_document_at(idx).unwrap();
                black_box(doc);
            }
        });
    });

    group.finish();
}

criterion_group!(
    benches,
    bench_get_by_id,
    bench_get_by_index,
    bench_random_batch
);
criterion_main!(benches);
