//! Node.js bindings for ZDS using napi-rs.

use std::sync::Mutex;

use napi::bindgen_prelude::*;
use napi_derive::napi;
use zippy_data::{FastStore, OpenMode, ZDSRoot as RustZDSRoot};

/// High-performance ZDS Store backed by Rust FastStore (JSONL-based).
#[napi]
pub struct ZDSStore {
    store: Mutex<FastStore>,
    root: String,
    collection: String,
}

#[napi]
impl ZDSStore {
    /// Open a ZDS store.
    #[napi(factory)]
    pub fn open(root: String, collection: Option<String>, batch_size: Option<u32>) -> Result<Self> {
        let collection = collection.unwrap_or_else(|| "default".to_string());
        let batch_size = batch_size.unwrap_or(5000) as usize;

        let store = FastStore::open(&root, &collection, batch_size)
            .map_err(|e| Error::from_reason(format!("Failed to open store: {}", e)))?;

        Ok(ZDSStore {
            store: Mutex::new(store),
            root,
            collection,
        })
    }

    /// Get document by ID.
    #[napi]
    pub fn get(&self, doc_id: String) -> Result<serde_json::Value> {
        let store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;
        store
            .get(&doc_id)
            .map_err(|_| Error::from_reason(format!("Document not found: {}", doc_id)))
    }

    /// Put a document.
    #[napi]
    pub fn put(&self, doc_id: String, doc: serde_json::Value) -> Result<()> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;
        store
            .put(doc_id, doc)
            .map_err(|e| Error::from_reason(format!("Write failed: {}", e)))
    }

    /// Delete a document.
    #[napi]
    pub fn delete(&self, doc_id: String) -> Result<()> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;
        store
            .delete(&doc_id)
            .map_err(|e| Error::from_reason(format!("Delete failed: {}", e)))
    }

    /// Flush pending writes and refresh mmap.
    #[napi]
    pub fn flush(&self) -> Result<()> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;
        store
            .flush()
            .map_err(|e| Error::from_reason(format!("Flush failed: {}", e)))?;
        store
            .refresh_mmap()
            .map_err(|e| Error::from_reason(format!("Mmap refresh failed: {}", e)))
    }

    /// Close the store and flush pending writes.
    #[napi]
    pub fn close(&self) -> Result<()> {
        self.flush()
    }

    /// Write a complete JSONL blob (fastest bulk write path).
    /// jsonl_data: Pre-serialized JSONL with one JSON object per line.
    /// doc_ids: List of document IDs in order matching the lines.
    #[napi]
    pub fn write_jsonl(&self, jsonl_data: Buffer, doc_ids: Vec<String>) -> Result<u32> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;
        let count = store
            .write_jsonl_blob(&jsonl_data, &doc_ids)
            .map_err(|e| Error::from_reason(format!("Write failed: {}", e)))?;
        Ok(count as u32)
    }

    /// Scan and return raw JSON bytes (fastest read path).
    #[napi]
    pub fn scan_raw(&self) -> Result<Vec<Buffer>> {
        let store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;
        let raw = store
            .scan_raw()
            .map_err(|e| Error::from_reason(format!("Scan failed: {}", e)))?;
        Ok(raw.into_iter().map(Buffer::from).collect())
    }

    /// Read entire JSONL file as a single buffer (fastest bulk read).
    /// Returns the raw JSONL content - caller splits and parses.
    #[napi]
    pub fn read_jsonl_blob(&self) -> Result<Buffer> {
        let store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;

        // Get mmap data directly via the public method
        if let Some(data) = store.get_raw_data() {
            Ok(Buffer::from(data.to_vec()))
        } else {
            Ok(Buffer::from(Vec::new()))
        }
    }

    /// Get document count.
    #[napi(getter)]
    pub fn count(&self) -> u32 {
        self.store.lock().map(|s| s.len() as u32).unwrap_or(0)
    }

    /// Check if document exists.
    #[napi]
    pub fn exists(&self, doc_id: String) -> bool {
        self.store
            .lock()
            .map(|s| s.exists(&doc_id))
            .unwrap_or(false)
    }

    /// Scan all documents.
    #[napi]
    pub fn scan(&self) -> Result<Vec<serde_json::Value>> {
        let store = self
            .store
            .lock()
            .map_err(|e| Error::from_reason(format!("Lock error: {}", e)))?;
        store
            .scan()
            .map_err(|e| Error::from_reason(format!("Scan failed: {}", e)))
    }

    /// List all document IDs.
    #[napi]
    pub fn list_doc_ids(&self) -> Vec<String> {
        self.store.lock().map(|s| s.doc_ids()).unwrap_or_default()
    }

    /// Get store info.
    #[napi(getter)]
    pub fn info(&self) -> StoreInfo {
        let count = self.store.lock().map(|s| s.len() as u32).unwrap_or(0);
        StoreInfo {
            root: self.root.clone(),
            collection: self.collection.clone(),
            count,
        }
    }
}

/// Store information.
#[napi(object)]
pub struct StoreInfo {
    pub root: String,
    pub collection: String,
    pub count: u32,
}

/// Get the ZDS version.
#[napi]
pub fn version() -> &'static str {
    zippy_data::ZDS_VERSION
}

/// Bulk write helper for high-throughput ingestion.
#[napi]
pub struct BulkWriter {
    store: FastStore,
}

#[napi]
impl BulkWriter {
    /// Create a new bulk writer.
    #[napi(factory)]
    pub fn create(
        root: String,
        collection: Option<String>,
        batch_size: Option<u32>,
    ) -> Result<Self> {
        let collection = collection.unwrap_or_else(|| "default".to_string());
        let batch_size = batch_size.unwrap_or(10000) as usize;

        let store = FastStore::open(&root, &collection, batch_size)
            .map_err(|e| Error::from_reason(format!("Failed to create store: {}", e)))?;

        Ok(BulkWriter { store })
    }

    /// Put a document.
    #[napi]
    pub fn put(&mut self, doc_id: String, doc: serde_json::Value) -> Result<()> {
        self.store
            .put(doc_id, doc)
            .map_err(|e| Error::from_reason(format!("Write failed: {}", e)))
    }

    /// Flush pending writes.
    #[napi]
    pub fn flush(&mut self) -> Result<()> {
        self.store
            .flush()
            .map_err(|e| Error::from_reason(format!("Flush failed: {}", e)))
    }

    /// Get current document count.
    #[napi(getter)]
    pub fn count(&self) -> u32 {
        self.store.len() as u32
    }
}

/// Root handle for a ZDS store directory.
///
/// This class represents a ZDS root directory without binding to a specific collection.
/// It allows opening multiple collections from the same root safely, avoiding corruption
/// when writing to multiple collections simultaneously.
///
/// Example:
///   const root = ZdsRoot.open('./data');
///   const train = root.collection('train');
///   const test = root.collection('test');
///   train.put('doc1', { split: 'train' });
///   test.put('doc1', { split: 'test' });
#[napi(js_name = "ZdsRoot")]
pub struct ZDSRoot {
    root: RustZDSRoot,
}

#[napi]
impl ZDSRoot {
    /// Open or create a ZDS root directory.
    ///
    /// @param root - Path to the ZDS root directory
    /// @param batchSize - Default batch size for collections (default: 5000)
    /// @param mode - Open mode: "r" for read-only, "rw" for read-write (default: "rw")
    #[napi(factory)]
    pub fn open(root: String, batch_size: Option<u32>, mode: Option<String>) -> Result<Self> {
        let batch_size = batch_size.unwrap_or(5000) as usize;
        let mode_str = mode.as_deref().unwrap_or("rw");

        let open_mode = match mode_str {
            "r" | "read" => OpenMode::Read,
            "rw" | "read-write" | "readwrite" => OpenMode::ReadWrite,
            _ => return Err(Error::from_reason(format!(
                "Invalid mode '{}'. Use 'r' for read-only or 'rw' for read-write", mode_str
            ))),
        };

        let zds_root = RustZDSRoot::open(&root, batch_size, open_mode)
            .map_err(|e| Error::from_reason(format!("Failed to open root: {}", e)))?;

        Ok(ZDSRoot { root: zds_root })
    }

    /// Get the root path.
    #[napi(getter)]
    pub fn root_path(&self) -> String {
        self.root.root_path().to_string_lossy().to_string()
    }

    /// Get the default batch size.
    #[napi(getter)]
    pub fn batch_size(&self) -> u32 {
        self.root.batch_size() as u32
    }

    /// Get the open mode ("r" or "rw").
    #[napi(getter)]
    pub fn mode(&self) -> &'static str {
        match self.root.mode() {
            OpenMode::Read => "r",
            OpenMode::ReadWrite => "rw",
        }
    }

    /// Check if this root is writable.
    #[napi(getter)]
    pub fn is_writable(&self) -> bool {
        self.root.is_writable()
    }

    /// Open a collection within this ZDS root.
    #[napi]
    pub fn collection(&self, name: String, batch_size: Option<u32>) -> Result<ZDSStore> {
        let store = if let Some(bs) = batch_size {
            self.root.collection_with_batch_size(&name, bs as usize)
        } else {
            self.root.collection(&name)
        }
        .map_err(|e| Error::from_reason(format!("Failed to open collection: {}", e)))?;

        Ok(ZDSStore {
            store: Mutex::new(store),
            root: self.root.root_path().to_string_lossy().to_string(),
            collection: name,
        })
    }

    /// List all collections in this ZDS root.
    #[napi]
    pub fn list_collections(&self) -> Result<Vec<String>> {
        self.root
            .list_collections()
            .map_err(|e| Error::from_reason(format!("Failed to list collections: {}", e)))
    }

    /// Check if a collection exists.
    #[napi]
    pub fn collection_exists(&self, name: String) -> bool {
        self.root.collection_exists(&name)
    }

    /// Close the root and release any locks.
    #[napi]
    pub fn close(&self) {
        self.root.close();
    }

    /// Get root info.
    #[napi(getter)]
    pub fn info(&self) -> RootInfo {
        let collections = self.root.list_collections().unwrap_or_default();
        RootInfo {
            root: self.root.root_path().to_string_lossy().to_string(),
            batch_size: self.root.batch_size() as u32,
            mode: self.mode().to_string(),
            is_writable: self.root.is_writable(),
            collections,
        }
    }
}

/// Root information.
#[napi(object)]
pub struct RootInfo {
    pub root: String,
    pub batch_size: u32,
    pub mode: String,
    pub is_writable: bool,
    pub collections: Vec<String>,
}
