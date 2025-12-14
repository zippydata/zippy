//! Comparative benchmarks: ZDS vs SQLite vs Sled
//!
//! This benchmark compares ZDS performance against other Rust storage solutions
//! for document/JSON workloads.
//!
//! Run with: cargo bench -- comparison

use std::path::PathBuf;

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use rand::Rng;
use rusqlite::{params, Connection};
use serde_json::json;
use tempfile::TempDir;
use zippy_data::{FastStore, Layout};

const RECORD_COUNTS: &[usize] = &[1000, 10000, 100000];
const RANDOM_LOOKUP_COUNT: usize = 1000;

/// Generate a sample document with ~200 bytes
fn generate_doc(i: usize) -> serde_json::Value {
    json!({
        "id": format!("record_{:08}", i),
        "name": format!("User {}", i),
        "email": format!("user{}@example.com", i),
        "age": 20 + (i % 60),
        "score": (i as f64) * 0.87 + 12.5,
        "active": i % 2 == 0,
        "tags": ["tag_a", "tag_b", "tag_c"],
        "metadata": {
            "created": "2025-01-15",
            "source": "benchmark"
        }
    })
}

// =============================================================================
// ZDS Setup
// =============================================================================

fn setup_zds(count: usize) -> (TempDir, PathBuf) {
    let tmp = TempDir::new().unwrap();
    let root = tmp.path().to_path_buf();
    Layout::init_root(&root).unwrap();

    let mut store = FastStore::open(&root, "bench", 1000).unwrap();
    for i in 0..count {
        store
            .put(format!("record_{:08}", i), generate_doc(i))
            .unwrap();
    }
    store.flush().unwrap();

    (tmp, root)
}

// =============================================================================
// SQLite Setup
// =============================================================================

fn setup_sqlite(count: usize) -> (TempDir, PathBuf) {
    let tmp = TempDir::new().unwrap();
    let db_path = tmp.path().join("bench.db");

    let conn = Connection::open(&db_path).unwrap();
    conn.execute_batch(
        "
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        CREATE TABLE docs (id TEXT PRIMARY KEY, data TEXT);
    ",
    )
    .unwrap();

    {
        let mut stmt = conn
            .prepare("INSERT INTO docs (id, data) VALUES (?, ?)")
            .unwrap();
        for i in 0..count {
            let id = format!("record_{:08}", i);
            let data = serde_json::to_string(&generate_doc(i)).unwrap();
            stmt.execute(params![id, data]).unwrap();
        }
    }

    (tmp, db_path)
}

// =============================================================================
// Sled Setup
// =============================================================================

fn setup_sled(count: usize) -> (TempDir, PathBuf) {
    let tmp = TempDir::new().unwrap();
    let db_path = tmp.path().join("sled_db");

    let db = sled::open(&db_path).unwrap();
    for i in 0..count {
        let id = format!("record_{:08}", i);
        let data = serde_json::to_string(&generate_doc(i)).unwrap();
        db.insert(id.as_bytes(), data.as_bytes()).unwrap();
    }
    db.flush().unwrap();

    (tmp, db_path)
}

// =============================================================================
// Write Benchmarks
// =============================================================================

fn bench_write(c: &mut Criterion) {
    let mut group = c.benchmark_group("write");

    for count in RECORD_COUNTS.iter().take(2) {
        // Skip 100k for write (too slow)
        group.throughput(Throughput::Elements(*count as u64));

        // ZDS
        group.bench_with_input(BenchmarkId::new("zds", count), count, |b, &count| {
            b.iter_with_setup(
                || {
                    let tmp = TempDir::new().unwrap();
                    let root = tmp.path().to_path_buf();
                    Layout::init_root(&root).unwrap();
                    (tmp, root)
                },
                |(_tmp, root)| {
                    let mut store = FastStore::open(&root, "bench", 1000).unwrap();
                    for i in 0..count {
                        store
                            .put(format!("record_{:08}", i), generate_doc(i))
                            .unwrap();
                    }
                    store.flush().unwrap();
                    black_box(())
                },
            );
        });

        // SQLite
        group.bench_with_input(BenchmarkId::new("sqlite", count), count, |b, &count| {
            b.iter_with_setup(
                || {
                    let tmp = TempDir::new().unwrap();
                    let db_path = tmp.path().join("bench.db");
                    (tmp, db_path)
                },
                |(_tmp, db_path)| {
                    let conn = Connection::open(&db_path).unwrap();
                    conn.execute_batch(
                        "
                        PRAGMA journal_mode = WAL;
                        PRAGMA synchronous = NORMAL;
                        CREATE TABLE docs (id TEXT PRIMARY KEY, data TEXT);
                    ",
                    )
                    .unwrap();

                    let mut stmt = conn
                        .prepare("INSERT INTO docs (id, data) VALUES (?, ?)")
                        .unwrap();
                    for i in 0..count {
                        let id = format!("record_{:08}", i);
                        let data = serde_json::to_string(&generate_doc(i)).unwrap();
                        stmt.execute(params![id, data]).unwrap();
                    }
                    black_box(())
                },
            );
        });

        // Sled
        group.bench_with_input(BenchmarkId::new("sled", count), count, |b, &count| {
            b.iter_with_setup(
                || {
                    let tmp = TempDir::new().unwrap();
                    let db_path = tmp.path().join("sled_db");
                    (tmp, db_path)
                },
                |(_tmp, db_path)| {
                    let db = sled::open(&db_path).unwrap();
                    for i in 0..count {
                        let id = format!("record_{:08}", i);
                        let data = serde_json::to_string(&generate_doc(i)).unwrap();
                        db.insert(id.as_bytes(), data.as_bytes()).unwrap();
                    }
                    db.flush().unwrap();
                    black_box(())
                },
            );
        });
    }

    group.finish();
}

// =============================================================================
// Read All Benchmarks
// =============================================================================

fn bench_read_all(c: &mut Criterion) {
    let mut group = c.benchmark_group("read_all");

    for count in RECORD_COUNTS.iter() {
        group.throughput(Throughput::Elements(*count as u64));

        // ZDS - Cold (includes open)
        let (zds_tmp, zds_root) = setup_zds(*count);
        group.bench_with_input(BenchmarkId::new("zds_cold", count), count, |b, _| {
            b.iter(|| {
                let store = FastStore::open(&zds_root, "bench", 1000).unwrap();
                let docs = store.scan().unwrap();
                black_box(docs.len())
            });
        });

        // ZDS - Warm (store already open)
        let warm_store = FastStore::open(&zds_root, "bench", 1000).unwrap();
        group.bench_with_input(BenchmarkId::new("zds_warm", count), count, |b, _| {
            b.iter(|| {
                let docs = warm_store.scan().unwrap();
                black_box(docs.len())
            });
        });
        drop(warm_store);
        drop(zds_tmp);

        // SQLite - Cold
        let (sqlite_tmp, sqlite_path) = setup_sqlite(*count);
        group.bench_with_input(BenchmarkId::new("sqlite_cold", count), count, |b, _| {
            b.iter(|| {
                let conn = Connection::open(&sqlite_path).unwrap();
                let mut stmt = conn.prepare("SELECT data FROM docs").unwrap();
                let docs: Vec<String> = stmt
                    .query_map([], |row| row.get(0))
                    .unwrap()
                    .filter_map(|r| r.ok())
                    .collect();
                black_box(docs.len())
            });
        });

        // SQLite - Warm
        let warm_conn = Connection::open(&sqlite_path).unwrap();
        group.bench_with_input(BenchmarkId::new("sqlite_warm", count), count, |b, _| {
            b.iter(|| {
                let mut stmt = warm_conn.prepare_cached("SELECT data FROM docs").unwrap();
                let docs: Vec<String> = stmt
                    .query_map([], |row| row.get(0))
                    .unwrap()
                    .filter_map(|r| r.ok())
                    .collect();
                black_box(docs.len())
            });
        });
        drop(warm_conn);
        drop(sqlite_tmp);

        // Sled - Cold
        let (sled_tmp, sled_path) = setup_sled(*count);
        group.bench_with_input(BenchmarkId::new("sled_cold", count), count, |b, _| {
            b.iter(|| {
                let db = sled::open(&sled_path).unwrap();
                let docs: Vec<_> = db.iter().filter_map(|r| r.ok()).collect();
                black_box(docs.len())
            });
        });

        // Sled - Warm
        let warm_db = sled::open(&sled_path).unwrap();
        group.bench_with_input(BenchmarkId::new("sled_warm", count), count, |b, _| {
            b.iter(|| {
                let docs: Vec<_> = warm_db.iter().filter_map(|r| r.ok()).collect();
                black_box(docs.len())
            });
        });
        drop(warm_db);
        drop(sled_tmp);
    }

    group.finish();
}

// =============================================================================
// Random Access Benchmarks
// =============================================================================

fn bench_random_access(c: &mut Criterion) {
    let mut group = c.benchmark_group("random_access");
    let count = 10000;

    group.throughput(Throughput::Elements(RANDOM_LOOKUP_COUNT as u64));

    // Generate random IDs to lookup
    let mut rng = rand::thread_rng();
    let lookup_ids: Vec<String> = (0..RANDOM_LOOKUP_COUNT)
        .map(|_| format!("record_{:08}", rng.gen_range(0..count)))
        .collect();

    // ZDS
    let (zds_tmp, zds_root) = setup_zds(count);
    let zds_store = FastStore::open(&zds_root, "bench", 1000).unwrap();
    group.bench_function("zds", |b| {
        b.iter(|| {
            for id in &lookup_ids {
                let doc = zds_store.get(id).unwrap();
                black_box(doc);
            }
        });
    });
    drop(zds_store);
    drop(zds_tmp);

    // SQLite
    let (sqlite_tmp, sqlite_path) = setup_sqlite(count);
    let sqlite_conn = Connection::open(&sqlite_path).unwrap();
    group.bench_function("sqlite", |b| {
        b.iter(|| {
            for id in &lookup_ids {
                let mut stmt = sqlite_conn
                    .prepare_cached("SELECT data FROM docs WHERE id = ?")
                    .unwrap();
                let doc: String = stmt.query_row(params![id], |row| row.get(0)).unwrap();
                black_box(doc);
            }
        });
    });
    drop(sqlite_conn);
    drop(sqlite_tmp);

    // Sled
    let (sled_tmp, sled_path) = setup_sled(count);
    let sled_db = sled::open(&sled_path).unwrap();
    group.bench_function("sled", |b| {
        b.iter(|| {
            for id in &lookup_ids {
                let doc = sled_db.get(id.as_bytes()).unwrap().unwrap();
                black_box(doc);
            }
        });
    });
    drop(sled_db);
    drop(sled_tmp);

    group.finish();
}

criterion_group!(benches, bench_write, bench_read_all, bench_random_access);
criterion_main!(benches);
