//! Streaming and bulk data examples with ZDS.
//!
//! This example demonstrates:
//! - High-throughput bulk ingestion with FastStore
//! - Parallel processing with scan_parallel
//! - Raw JSONL blob operations
//! - Memory-efficient iteration
//!
//! Run: cargo run --bin streaming_data

use anyhow::Result;
use rand::Rng;
use serde_json::json;
use std::path::PathBuf;
use std::time::Instant;
use zippy_data::{FastStore, Layout};

fn main() -> Result<()> {
    let data_path = setup_data_dir()?;
    println!("Output directory: {}\n", data_path.display());

    example_bulk_ingestion(&data_path)?;
    example_scan_all(&data_path)?;
    example_raw_jsonl(&data_path)?;
    example_filtered_processing(&data_path)?;

    println!("\n{}", "=".repeat(60));
    println!("All examples completed successfully!");
    println!("Data saved to: {}", data_path.display());
    println!("{}", "=".repeat(60));

    Ok(())
}

fn setup_data_dir() -> Result<PathBuf> {
    let data_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("data")
        .join("rust_02_streaming");

    if data_path.exists() {
        std::fs::remove_dir_all(&data_path)?;
    }
    std::fs::create_dir_all(&data_path)?;
    Layout::init_root(&data_path)?;

    Ok(data_path)
}

fn example_bulk_ingestion(data_path: &PathBuf) -> Result<()> {
    println!("{}", "=".repeat(60));
    println!("Example 1: Bulk Ingestion");
    println!("{}", "=".repeat(60));

    let mut store = FastStore::open(data_path, "events", 500)?;
    let mut rng = rand::thread_rng();
    let count = 50_000;

    let start = Instant::now();

    for i in 0..count {
        let event_types = ["click", "view", "purchase", "signup"];
        let browsers = ["Chrome", "Firefox", "Safari", "Edge"];
        let platforms = ["Windows", "Mac", "Linux", "Mobile"];

        store.put(
            format!("event_{:06}", i),
            json!({
                "id": i,
                "timestamp": chrono::Utc::now().to_rfc3339(),
                "type": event_types[i % 4],
                "user_id": format!("user_{:03}", i % 100),
                "value": rng.gen::<f64>() * 1000.0,
                "metadata": {
                    "browser": browsers[i % 4],
                    "platform": platforms[i % 4],
                    "session_id": format!("sess_{:08}", rng.gen::<u32>())
                }
            }),
        )?;
    }

    store.flush()?;

    let elapsed = start.elapsed();
    let rate = count as f64 / elapsed.as_secs_f64();

    println!("Wrote {} events in {:?}", count, elapsed);
    println!("Rate: {:.0} docs/sec", rate);
    println!("\nData saved to: {}/collections/events/", data_path.display());

    Ok(())
}

fn example_scan_all(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 2: Scan All Documents");
    println!("{}", "=".repeat(60));

    let store = FastStore::open(data_path, "events", 100)?;

    let start = Instant::now();

    // Scan all and compute aggregates
    let mut count = 0;
    let mut total_value = 0.0;
    let mut type_counts: std::collections::HashMap<String, usize> = std::collections::HashMap::new();

    let docs = store.scan_all()?;
    for doc in docs {
        count += 1;
        if let Some(val) = doc["value"].as_f64() {
            total_value += val;
        }
        if let Some(t) = doc["type"].as_str() {
            *type_counts.entry(t.to_string()).or_insert(0) += 1;
        }
    }

    let elapsed = start.elapsed();

    println!("Scanned {} documents in {:?}", count, elapsed);
    println!("\nEvent counts by type:");
    for (event_type, cnt) in &type_counts {
        println!("  {}: {}", event_type, cnt);
    }
    println!("\nTotal value: {:.2}", total_value);
    println!("Average value: {:.2}", total_value / count as f64);

    Ok(())
}

fn example_raw_jsonl(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 3: Raw JSONL Blob Operations");
    println!("{}", "=".repeat(60));

    let store = FastStore::open(data_path, "events", 100)?;

    let start = Instant::now();

    // Read entire JSONL as blob (fastest read path)
    let blob = store.read_jsonl_blob()?;

    let elapsed = start.elapsed();
    println!("Read {} bytes in {:?}", blob.len(), elapsed);

    // Count lines using memchr (SIMD)
    let parse_start = Instant::now();
    let line_count = blob.iter().filter(|&&b| b == b'\n').count();
    let parse_elapsed = parse_start.elapsed();

    println!("Counted {} lines in {:?}", line_count, parse_elapsed);

    Ok(())
}

fn example_filtered_processing(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 4: Filtered Processing");
    println!("{}", "=".repeat(60));

    let source = FastStore::open(data_path, "events", 100)?;
    let mut target = FastStore::open(data_path, "purchases", 100)?;

    let start = Instant::now();

    // Filter purchases and transform
    let docs = source.scan_all()?;
    let mut purchase_count = 0;

    for doc in docs {
        if doc["type"].as_str() == Some("purchase") {
            target.put(
                format!("purchase_{:04}", purchase_count),
                json!({
                    "original_id": doc["id"],
                    "user_id": doc["user_id"],
                    "amount": doc["value"],
                    "timestamp": doc["timestamp"],
                    "browser": doc["metadata"]["browser"]
                }),
            )?;
            purchase_count += 1;
        }
    }

    target.flush()?;

    let elapsed = start.elapsed();

    println!("Extracted {} purchases in {:?}", purchase_count, elapsed);
    println!("\nData saved to: {}/collections/purchases/", data_path.display());

    Ok(())
}
