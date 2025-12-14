//! Benchmarks for sequential scanning.

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
            "email": format!("user{}@example.com", i),
            "age": 20 + (i % 60),
            "active": i % 2 == 0,
            "score": i as f64 * 1.5,
            "tags": ["tag1", "tag2", "tag3"],
            "metadata": {
                "created": "2025-01-01",
                "version": 1
            }
        });
        writer.put(format!("doc{:06}", i), doc).unwrap();
    }
    writer.flush().unwrap();

    (tmp, root)
}

fn bench_full_scan(c: &mut Criterion) {
    let mut group = c.benchmark_group("scan");

    for count in [100, 1000, 10000].iter() {
        let (_tmp, root) = setup_benchmark_data(*count);

        group.bench_with_input(BenchmarkId::new("full_scan", count), count, |b, _| {
            let engine = Engine::open(&root, "bench").unwrap();
            b.iter(|| {
                let scanner = engine.scan(None, None).unwrap();
                let docs: Vec<_> = scanner.collect();
                black_box(docs)
            });
        });
    }

    group.finish();
}

fn bench_projected_scan(c: &mut Criterion) {
    let (_tmp, root) = setup_benchmark_data(10000);

    let mut group = c.benchmark_group("scan_projection");

    group.bench_function("all_fields", |b| {
        let engine = Engine::open(&root, "bench").unwrap();
        b.iter(|| {
            let scanner = engine.scan(None, None).unwrap();
            let docs: Vec<_> = scanner.collect();
            black_box(docs)
        });
    });

    group.bench_function("two_fields", |b| {
        let engine = Engine::open(&root, "bench").unwrap();
        b.iter(|| {
            let scanner = engine.scan(None, Some(&["name", "age"])).unwrap();
            let docs: Vec<_> = scanner.collect();
            black_box(docs)
        });
    });

    group.finish();
}

fn bench_filtered_scan(c: &mut Criterion) {
    let (_tmp, root) = setup_benchmark_data(10000);

    let mut group = c.benchmark_group("scan_filter");

    group.bench_function("no_filter", |b| {
        let engine = Engine::open(&root, "bench").unwrap();
        b.iter(|| {
            let scanner = engine.scan(None, None).unwrap();
            let docs: Vec<_> = scanner.collect();
            black_box(docs)
        });
    });

    group.bench_function("equality_filter", |b| {
        let engine = Engine::open(&root, "bench").unwrap();
        let pred = zippy_data::Predicate::eq("active", true);
        b.iter(|| {
            let scanner = engine.scan(Some(&pred), None).unwrap();
            let docs: Vec<_> = scanner.collect();
            black_box(docs)
        });
    });

    group.finish();
}

criterion_group!(
    benches,
    bench_full_scan,
    bench_projected_scan,
    bench_filtered_scan
);
criterion_main!(benches);
