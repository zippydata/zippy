//! Node.js bindings for ZDS using napi-rs.

use napi::bindgen_prelude::*;
use napi_derive::napi;
use std::sync::Mutex;
use zippy_core::FastStore;

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
    zippy_core::ZDS_VERSION
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
