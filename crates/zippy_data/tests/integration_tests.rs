//! Integration tests for ZDS core functionality.
//!
//! These tests verify end-to-end workflows across multiple components.

use std::path::PathBuf;

use serde_json::json;
use tempfile::TempDir;
use zippy_data::{
    writer::{BufferedWriter, SyncWriter, WriteConfig},
    Engine, FastStore, Layout, Result,
};

/// Create a temporary test directory with proper layout.
fn setup_test_dir() -> (TempDir, PathBuf) {
    let tmp = TempDir::new().unwrap();
    let root = tmp.path().to_path_buf();
    Layout::init_root(&root).unwrap();
    (tmp, root)
}

// =============================================================================
// FastStore Integration Tests
// =============================================================================

mod fast_store {
    use super::*;

    #[test]
    fn test_basic_crud_workflow() -> Result<()> {
        let (_tmp, root) = setup_test_dir();
        let mut store = FastStore::open(&root, "test", 100)?;

        // Create
        store.put("doc1", json!({"name": "Alice", "age": 30}))?;
        store.put("doc2", json!({"name": "Bob", "age": 25}))?;
        store.flush()?;

        assert_eq!(store.len(), 2);

        // Read
        let doc1 = store.get("doc1")?;
        assert_eq!(doc1["name"], "Alice");

        // Update
        store.put("doc1", json!({"name": "Alice", "age": 31}))?;
        store.flush()?;

        let doc1_updated = store.get("doc1")?;
        assert_eq!(doc1_updated["age"], 31);

        // Delete
        store.delete("doc2")?;
        assert_eq!(store.len(), 1);
        assert!(!store.exists("doc2"));

        Ok(())
    }

    #[test]
    fn test_persistence_across_sessions() -> Result<()> {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path().to_path_buf();
        Layout::init_root(&root)?;

        // Session 1: Write data
        {
            let mut store = FastStore::open(&root, "persist", 100)?;
            store.put("doc1", json!({"session": 1}))?;
            store.put("doc2", json!({"session": 1}))?;
            store.flush()?;
        }

        // Session 2: Read and verify
        {
            let store = FastStore::open(&root, "persist", 100)?;
            assert_eq!(store.len(), 2);

            let doc1 = store.get("doc1")?;
            assert_eq!(doc1["session"], 1);
        }

        // Session 3: Add more data
        {
            let mut store = FastStore::open(&root, "persist", 100)?;
            store.put("doc3", json!({"session": 3}))?;
            store.flush()?;
            assert_eq!(store.len(), 3);
        }

        Ok(())
    }

    #[test]
    fn test_bulk_ingestion() -> Result<()> {
        let (_tmp, root) = setup_test_dir();
        let mut store = FastStore::open(&root, "bulk", 500)?;

        for i in 0..10000 {
            let category = match i % 3 {
                0 => "A",
                1 => "B",
                _ => "C",
            };
            store.put(
                format!("doc_{:06}", i),
                json!({
                    "id": i,
                    "value": i * 2,
                    "category": category
                }),
            )?;
        }
        store.flush()?;

        assert_eq!(store.len(), 10000);

        // Verify random samples
        let doc_0 = store.get("doc_000000")?;
        assert_eq!(doc_0["id"], 0);

        let doc_5000 = store.get("doc_005000")?;
        assert_eq!(doc_5000["id"], 5000);

        let doc_9999 = store.get("doc_009999")?;
        assert_eq!(doc_9999["id"], 9999);

        Ok(())
    }

    #[test]
    fn test_scan_all() -> Result<()> {
        let (_tmp, root) = setup_test_dir();
        let mut store = FastStore::open(&root, "scan", 100)?;

        for i in 0..100 {
            store.put(format!("doc_{}", i), json!({"index": i}))?;
        }
        store.flush()?;

        let docs = store.scan()?;
        assert_eq!(docs.len(), 100);

        Ok(())
    }

    #[test]
    fn test_read_jsonl_blob() -> Result<()> {
        let (_tmp, root) = setup_test_dir();
        let mut store = FastStore::open(&root, "jsonl", 100)?;

        store.put("doc1", json!({"value": 1}))?;
        store.put("doc2", json!({"value": 2}))?;
        store.flush()?;

        let raw = store.scan_raw()?;
        assert_eq!(raw.len(), 2);

        for line in raw {
            let doc: serde_json::Value = serde_json::from_slice(&line)?;
            assert!(doc.get("value").is_some());
        }

        Ok(())
    }

    #[test]
    fn test_nested_documents() -> Result<()> {
        let (_tmp, root) = setup_test_dir();
        let mut store = FastStore::open(&root, "nested", 100)?;

        let doc = json!({
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep",
                        "array": [1, 2, {"nested": true}]
                    }
                }
            }
        });

        store.put("nested", doc.clone())?;
        store.flush()?;

        let retrieved = store.get("nested")?;
        assert_eq!(retrieved["level1"]["level2"]["level3"]["value"], "deep");
        assert_eq!(
            retrieved["level1"]["level2"]["level3"]["array"][2]["nested"],
            true
        );

        Ok(())
    }
}

// =============================================================================
// Engine Integration Tests
// =============================================================================

mod engine {
    use super::*;

    #[test]
    fn test_engine_open_and_read() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        // Write with SyncWriter
        let mut writer = SyncWriter::new(&root, "test")?;
        writer.put("doc1", &json!({"name": "Alice"}))?;
        writer.put("doc2", &json!({"name": "Bob"}))?;
        writer.put("doc3", &json!({"name": "Charlie"}))?;

        // Read with Engine
        let engine = Engine::open(&root, "test")?;
        assert_eq!(engine.len(), 3);

        let doc = engine.get_document("doc1")?;
        assert_eq!(doc["name"], "Alice");

        Ok(())
    }

    #[test]
    fn test_engine_scan_with_predicate() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        let mut writer = SyncWriter::new(&root, "test")?;
        writer.put("doc1", &json!({"category": "A", "value": 10}))?;
        writer.put("doc2", &json!({"category": "B", "value": 20}))?;
        writer.put("doc3", &json!({"category": "A", "value": 30}))?;

        let engine = Engine::open(&root, "test")?;

        let pred = zippy_data::Predicate::eq("category", "A");
        let scanner = engine.scan(Some(&pred), None)?;
        let docs: Vec<serde_json::Value> = scanner.collect::<Result<Vec<_>>>()?;

        assert_eq!(docs.len(), 2);

        Ok(())
    }

    #[test]
    fn test_engine_scan_with_projection() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        let mut writer = SyncWriter::new(&root, "test")?;
        writer.put(
            "doc1",
            &json!({"name": "Alice", "age": 30, "email": "alice@example.com"}),
        )?;

        let engine = Engine::open(&root, "test")?;

        let scanner = engine.scan(None, Some(&["name", "age"]))?;
        let docs: Vec<serde_json::Value> = scanner.collect::<Result<Vec<_>>>()?;

        assert_eq!(docs.len(), 1);
        assert!(docs[0].get("name").is_some());
        assert!(docs[0].get("age").is_some());
        assert!(docs[0].get("email").is_none());

        Ok(())
    }

    #[test]
    fn test_engine_stats() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        let mut writer = SyncWriter::new(&root, "test")?;
        for i in 0..10 {
            writer.put(&format!("doc_{}", i), &json!({"index": i}))?;
        }

        let engine = Engine::open(&root, "test")?;
        let stats = engine.stats();

        assert_eq!(stats.collection, "test");
        assert_eq!(stats.doc_count, 10);

        Ok(())
    }
}

// =============================================================================
// Writer Integration Tests
// =============================================================================

mod writers {
    use super::*;

    #[test]
    fn test_sync_writer() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        let mut writer = SyncWriter::new(&root, "sync")?;

        for i in 0..100 {
            writer.put(&format!("doc_{}", i), &json!({"index": i}))?;
        }

        // Verify files exist
        let docs_dir = root.join("collections").join("sync").join("docs");
        assert!(docs_dir.exists());

        Ok(())
    }

    #[test]
    fn test_buffered_writer() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        let config = WriteConfig {
            max_pending_ops: 1000,
            max_pending_bytes: 10 * 1024 * 1024,
            flush_interval_ms: 60000,
        };

        let mut writer = BufferedWriter::new(&root, "buffered", config)?;

        for i in 0..1000 {
            writer.put(format!("doc_{}", i), json!({"index": i}))?;
        }
        writer.flush()?;

        // Verify with Engine
        let engine = Engine::open(&root, "buffered")?;
        assert_eq!(engine.len(), 1000);

        Ok(())
    }
}

// =============================================================================
// Cross-Component Integration Tests
// =============================================================================

mod cross_component {
    use super::*;

    #[test]
    fn test_faststore_to_engine() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        // Write with FastStore
        {
            let mut store = FastStore::open(&root, "cross", 100)?;
            store.put("fast_doc1", json!({"source": "faststore"}))?;
            store.put("fast_doc2", json!({"source": "faststore"}))?;
            store.flush()?;
        }

        // Also write with SyncWriter (different storage mode)
        {
            let mut writer = SyncWriter::new(&root, "cross")?;
            writer.put("sync_doc1", &json!({"source": "syncwriter"}))?;
        }

        // Read with Engine (should see SyncWriter docs)
        let engine = Engine::open(&root, "cross")?;
        assert!(!engine.is_empty());

        Ok(())
    }

    #[test]
    fn test_multiple_collections() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        // Create multiple collections
        {
            let mut train = FastStore::open(&root, "train", 100)?;
            train.put("t1", json!({"split": "train"}))?;
            train.put("t2", json!({"split": "train"}))?;
            train.flush()?;
        }

        {
            let mut test = FastStore::open(&root, "test", 100)?;
            test.put("e1", json!({"split": "test"}))?;
            test.flush()?;
        }

        {
            let mut val = FastStore::open(&root, "validation", 100)?;
            val.put("v1", json!({"split": "validation"}))?;
            val.flush()?;
        }

        // Verify each collection independently
        let train = FastStore::open(&root, "train", 100)?;
        assert_eq!(train.len(), 2);

        let test = FastStore::open(&root, "test", 100)?;
        assert_eq!(test.len(), 1);

        let val = FastStore::open(&root, "validation", 100)?;
        assert_eq!(val.len(), 1);

        Ok(())
    }
}

// =============================================================================
// Layout and Container Tests
// =============================================================================

mod layout {
    use zippy_data::container::{pack, unpack};

    use super::*;

    #[test]
    fn test_layout_validation() -> Result<()> {
        let (_tmp, root) = setup_test_dir();

        // Valid layout
        assert!(Layout::validate(&root).is_ok());

        // Initialize collection
        Layout::init_collection(&root, "test")?;
        assert!(Layout::validate_collection(&root, "test").is_ok());

        Ok(())
    }

    #[test]
    fn test_pack_unpack() -> Result<()> {
        let tmp = TempDir::new()?;
        let source = tmp.path().join("source");
        let archive = tmp.path().join("archive.zds");
        let dest = tmp.path().join("dest");

        // Create source with data
        std::fs::create_dir_all(&source)?;
        Layout::init_root(&source)?;

        {
            let mut store = FastStore::open(&source, "data", 100)?;
            store.put("doc1", json!({"packed": true}))?;
            store.flush()?;
        }

        // Pack
        pack(&source, &archive)?;
        assert!(archive.exists());

        // Unpack
        unpack(&archive, &dest)?;
        assert!(dest.exists());

        // Verify unpacked data
        let store = FastStore::open(&dest, "data", 100)?;
        assert_eq!(store.len(), 1);

        Ok(())
    }
}
