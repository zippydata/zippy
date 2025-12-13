//! Basic ZDS usage examples - store operations.
//!
//! This example demonstrates core ZDS functionality:
//! - Creating and opening stores
//! - CRUD operations (put, get, delete)
//! - Scanning with predicates and projections
//! - Engine API and FastStore API
//!
//! Run: cargo run --bin basic_usage

use anyhow::Result;
use serde_json::json;
use std::path::PathBuf;
use zippy_core::{Engine, FastStore, Layout};

fn main() -> Result<()> {
    println!("ZDS Core Version: {}\n", zippy_core::ZDS_VERSION);

    let data_path = setup_data_dir()?;
    println!("Output directory: {}\n", data_path.display());

    example_faststore(&data_path)?;
    example_engine(&data_path)?;
    example_scanning(&data_path)?;
    example_statistics(&data_path)?;

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
        .join("rust_01_basic");

    if data_path.exists() {
        std::fs::remove_dir_all(&data_path)?;
    }
    std::fs::create_dir_all(&data_path)?;
    Layout::init_root(&data_path)?;

    Ok(data_path)
}

fn example_faststore(data_path: &PathBuf) -> Result<()> {
    println!("{}", "=".repeat(60));
    println!("Example 1: FastStore Operations (High-throughput JSONL)");
    println!("{}", "=".repeat(60));

    // Create a FastStore (JSONL-based, high performance)
    let mut store = FastStore::open(data_path, "users", 100)?;

    // Put documents
    store.put(
        "user_001",
        json!({
            "name": "Alice Smith",
            "email": "alice@example.com",
            "age": 28,
            "tags": ["developer", "rust"]
        }),
    )?;

    store.put(
        "user_002",
        json!({
            "name": "Bob Jones",
            "email": "bob@example.com",
            "age": 35,
            "tags": ["manager", "agile"]
        }),
    )?;

    store.put(
        "user_003",
        json!({
            "name": "Charlie Brown",
            "email": "charlie@example.com",
            "age": 42,
            "tags": ["developer", "rust", "python"]
        }),
    )?;

    // Flush writes to disk
    store.flush()?;

    println!("Store has {} documents", store.len());

    // Get a document
    let user = store.get("user_001")?;
    println!("Retrieved user_001: {}", user["name"]);

    // Check existence
    println!("user_001 exists: {}", store.exists("user_001"));
    println!("user_999 exists: {}", store.exists("user_999"));

    // List all IDs
    let doc_ids = store.doc_ids();
    println!("All IDs: {:?}", doc_ids);

    // Delete a document
    store.delete("user_002")?;
    println!("\nAfter delete: {} documents", store.len());

    // Add another user
    store.put(
        "user_004",
        json!({
            "name": "Diana Prince",
            "email": "diana@example.com",
            "age": 30,
            "tags": ["hero"]
        }),
    )?;
    store.flush()?;

    let diana = store.get("user_004")?;
    println!("Added user_004: {}", diana["name"]);

    println!("\nData saved to: {}/collections/users/", data_path.display());
    Ok(())
}

fn example_engine(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 2: Engine API (JSON file-based)");
    println!("{}", "=".repeat(60));

    use zippy_core::writer::SyncWriter;

    // Create collection with SyncWriter (individual JSON files)
    let mut writer = SyncWriter::new(data_path, "products")?;

    writer.put(
        "prod_001",
        &json!({
            "name": "Laptop",
            "price": 999.99,
            "category": "Electronics",
            "in_stock": true
        }),
    )?;

    writer.put(
        "prod_002",
        &json!({
            "name": "Mouse",
            "price": 29.99,
            "category": "Electronics",
            "in_stock": true
        }),
    )?;

    writer.put(
        "prod_003",
        &json!({
            "name": "Desk Chair",
            "price": 249.99,
            "category": "Furniture",
            "in_stock": false
        }),
    )?;

    // Open with Engine for reading
    let engine = Engine::open(data_path, "products")?;
    println!("Engine loaded {} products", engine.len());

    // Get by ID
    let laptop = engine.get_document("prod_001")?;
    println!("Product: {} - ${}", laptop["name"], laptop["price"]);

    // Get by index
    let first = engine.get_document_at(0)?;
    println!("First product: {}", first["name"]);

    println!("\nData saved to: {}/collections/products/", data_path.display());
    Ok(())
}

fn example_scanning(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 3: Scanning with Predicates and Projections");
    println!("{}", "=".repeat(60));

    let engine = Engine::open(data_path, "products")?;

    // Scan all documents
    println!("\nAll products:");
    let mut scanner = engine.scan(None, None)?;
    while let Some(doc) = scanner.next()? {
        println!("  - {} (${:.2})", doc["name"], doc["price"]);
    }

    // Scan with projection (only specific fields)
    println!("\nNames only (projection):");
    let mut scanner = engine.scan(None, Some(&["name"]))?;
    while let Some(doc) = scanner.next()? {
        println!("  - {:?}", doc);
    }

    // Scan with predicate
    use zippy_core::Predicate;
    println!("\nElectronics only (predicate):");
    let pred = Predicate::eq("category", "Electronics");
    let mut scanner = engine.scan(Some(&pred), None)?;
    while let Some(doc) = scanner.next()? {
        println!("  - {} ({})", doc["name"], doc["category"]);
    }

    Ok(())
}

fn example_statistics(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 4: Collection Statistics");
    println!("{}", "=".repeat(60));

    // Stats from Engine
    let engine = Engine::open(data_path, "products")?;
    let stats = engine.stats();

    println!("\nCollection: {}", stats.collection);
    println!("  Documents: {}", stats.doc_count);
    println!("  Schemas: {}", stats.schema_count);
    println!("  Total size: {} bytes", stats.total_size);
    println!("  Strict mode: {}", stats.strict_mode);

    // Doc IDs from Engine
    println!("\nDocument IDs: {:?}", engine.doc_ids());

    Ok(())
}
