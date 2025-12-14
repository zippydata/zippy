//! Buffered writer with crash-safe commits.

use std::{
    path::{Path, PathBuf},
    time::{Duration, Instant},
};

use serde_json::Value;

use crate::{
    index::DocIndexEntry,
    schema::SchemaRegistry,
    txlog::{JournalEntry, TransactionLog},
    Error, IndexRegistry, Layout, Result,
};

/// Write operation.
#[derive(Debug)]
enum WriteOp {
    Put { doc_id: String, doc: Value },
    Delete { doc_id: String },
}

/// Configuration for buffered writer.
#[derive(Debug, Clone)]
pub struct WriteConfig {
    /// Maximum pending operations before auto-flush
    pub max_pending_ops: usize,
    /// Maximum pending bytes before auto-flush
    pub max_pending_bytes: usize,
    /// Flush interval in milliseconds
    pub flush_interval_ms: u64,
}

impl Default for WriteConfig {
    fn default() -> Self {
        WriteConfig {
            max_pending_ops: 1000,
            max_pending_bytes: 10 * 1024 * 1024, // 10MB
            flush_interval_ms: 1000,
        }
    }
}

/// Buffered writer for high-throughput ingestion.
pub struct BufferedWriter {
    root: PathBuf,
    collection: String,
    config: WriteConfig,
    pending_ops: Vec<WriteOp>,
    pending_bytes: usize,
    last_flush: Instant,
    journal: TransactionLog,
    index: IndexRegistry,
    schema_registry: SchemaRegistry,
}

impl BufferedWriter {
    /// Create a new buffered writer.
    pub fn new(
        root: impl AsRef<Path>,
        collection: impl AsRef<str>,
        config: WriteConfig,
    ) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let collection = collection.as_ref().to_string();

        // Ensure collection exists
        Layout::init_collection(&root, &collection)?;

        // Load or create indexes
        let index = IndexRegistry::load(&root, &collection).unwrap_or_default();
        let schema_registry =
            SchemaRegistry::load(&root, &collection).unwrap_or_else(|_| SchemaRegistry::new(false));

        // Open transaction log
        let journal = TransactionLog::open(&root, &collection)?;

        Ok(BufferedWriter {
            root,
            collection,
            config,
            pending_ops: Vec::new(),
            pending_bytes: 0,
            last_flush: Instant::now(),
            journal,
            index,
            schema_registry,
        })
    }

    /// Queue a document for writing.
    pub fn put(&mut self, doc_id: impl Into<String>, doc: Value) -> Result<()> {
        let doc_id = doc_id.into();
        Layout::validate_doc_id(&doc_id)?;

        let doc_size = serde_json::to_string(&doc)?.len();
        self.pending_bytes += doc_size;
        self.pending_ops.push(WriteOp::Put { doc_id, doc });

        self.maybe_flush()?;
        Ok(())
    }

    /// Queue a document deletion.
    pub fn delete(&mut self, doc_id: impl Into<String>) -> Result<()> {
        let doc_id = doc_id.into();
        self.pending_ops.push(WriteOp::Delete { doc_id });

        self.maybe_flush()?;
        Ok(())
    }

    /// Check if we should auto-flush.
    fn maybe_flush(&mut self) -> Result<()> {
        let should_flush = self.pending_ops.len() >= self.config.max_pending_ops
            || self.pending_bytes >= self.config.max_pending_bytes
            || self.last_flush.elapsed() >= Duration::from_millis(self.config.flush_interval_ms);

        if should_flush {
            self.flush()?;
        }
        Ok(())
    }

    /// Flush all pending operations.
    pub fn flush(&mut self) -> Result<()> {
        if self.pending_ops.is_empty() {
            return Ok(());
        }

        let ops = std::mem::take(&mut self.pending_ops);
        self.pending_bytes = 0;
        self.last_flush = Instant::now();

        for op in ops {
            match op {
                WriteOp::Put { doc_id, doc } => {
                    self.write_doc(&doc_id, &doc)?;
                }
                WriteOp::Delete { doc_id } => {
                    self.delete_doc(&doc_id)?;
                }
            }
        }

        // Commit the batch
        self.journal.commit()?;

        // Save indexes
        self.index.save(&self.root, &self.collection)?;
        self.schema_registry.save(&self.root, &self.collection)?;

        Ok(())
    }

    /// Write a single document (crash-safe).
    fn write_doc(&mut self, doc_id: &str, doc: &Value) -> Result<()> {
        // Register schema
        let schema_id = self.schema_registry.register(doc)?;

        // Write to temp file first
        let docs_dir = Layout::docs_dir(&self.root, &self.collection);
        let final_path = Layout::doc_file(&self.root, &self.collection, doc_id);
        let tmp_path = docs_dir.join(format!(".{}.tmp", doc_id));

        std::fs::create_dir_all(&docs_dir)?;

        let content = serde_json::to_string_pretty(doc)?;
        let size = content.len() as u64;

        std::fs::write(&tmp_path, &content)?;

        // Log the PUT
        self.journal
            .append(&JournalEntry::put(doc_id, &schema_id, size))?;

        // Atomic rename
        std::fs::rename(&tmp_path, &final_path)?;

        // Update index
        let mtime = std::fs::metadata(&final_path)
            .ok()
            .and_then(|m| m.modified().ok())
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);

        self.index.put(DocIndexEntry {
            doc_id: doc_id.to_string(),
            schema_id,
            size,
            mtime,
        });

        Ok(())
    }

    /// Delete a single document.
    fn delete_doc(&mut self, doc_id: &str) -> Result<()> {
        let path = Layout::doc_file(&self.root, &self.collection, doc_id);

        if !path.exists() {
            return Err(Error::DocumentNotFound(doc_id.to_string()));
        }

        // Get schema_id before deletion for unregistration
        if let Some(entry) = self.index.get(doc_id) {
            self.schema_registry.unregister(&entry.schema_id);
        }

        // Log the DELETE
        self.journal.append(&JournalEntry::delete(doc_id))?;

        // Delete file
        std::fs::remove_file(&path)?;

        // Update index
        self.index.remove(doc_id);

        Ok(())
    }

    /// Get current document count.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    /// Check if collection is empty.
    pub fn is_empty(&self) -> bool {
        self.index.is_empty()
    }
}

impl Drop for BufferedWriter {
    fn drop(&mut self) {
        // Flush any remaining operations
        let _ = self.flush();
    }
}

/// Synchronous document writer (simpler API, lower throughput).
pub struct SyncWriter {
    root: PathBuf,
    collection: String,
    journal: TransactionLog,
    index: IndexRegistry,
    schema_registry: SchemaRegistry,
}

impl SyncWriter {
    /// Create a new synchronous writer.
    pub fn new(root: impl AsRef<Path>, collection: impl AsRef<str>) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let collection = collection.as_ref().to_string();

        Layout::init_collection(&root, &collection)?;

        let index = IndexRegistry::load(&root, &collection).unwrap_or_default();
        let schema_registry =
            SchemaRegistry::load(&root, &collection).unwrap_or_else(|_| SchemaRegistry::new(false));
        let journal = TransactionLog::open(&root, &collection)?;

        Ok(SyncWriter {
            root,
            collection,
            journal,
            index,
            schema_registry,
        })
    }

    /// Write a document synchronously.
    pub fn put(&mut self, doc_id: &str, doc: &Value) -> Result<()> {
        Layout::validate_doc_id(doc_id)?;

        let schema_id = self.schema_registry.register(doc)?;

        let docs_dir = Layout::docs_dir(&self.root, &self.collection);
        let final_path = Layout::doc_file(&self.root, &self.collection, doc_id);
        let tmp_path = docs_dir.join(format!(".{}.tmp", doc_id));

        std::fs::create_dir_all(&docs_dir)?;

        let content = serde_json::to_string_pretty(doc)?;
        let size = content.len() as u64;

        std::fs::write(&tmp_path, &content)?;
        self.journal
            .append(&JournalEntry::put(doc_id, &schema_id, size))?;
        std::fs::rename(&tmp_path, &final_path)?;

        let mtime = std::fs::metadata(&final_path)
            .ok()
            .and_then(|m| m.modified().ok())
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);

        self.index.put(DocIndexEntry {
            doc_id: doc_id.to_string(),
            schema_id,
            size,
            mtime,
        });

        self.journal.commit()?;
        self.index.save(&self.root, &self.collection)?;
        self.schema_registry.save(&self.root, &self.collection)?;

        Ok(())
    }

    /// Delete a document synchronously.
    pub fn delete(&mut self, doc_id: &str) -> Result<()> {
        let path = Layout::doc_file(&self.root, &self.collection, doc_id);

        if !path.exists() {
            return Err(Error::DocumentNotFound(doc_id.to_string()));
        }

        if let Some(entry) = self.index.get(doc_id) {
            self.schema_registry.unregister(&entry.schema_id);
        }

        self.journal.append(&JournalEntry::delete(doc_id))?;
        std::fs::remove_file(&path)?;
        self.index.remove(doc_id);
        self.journal.commit()?;
        self.index.save(&self.root, &self.collection)?;
        self.schema_registry.save(&self.root, &self.collection)?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;
    use tempfile::TempDir;

    use super::*;

    #[test]
    fn test_buffered_writer() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();
        Layout::init_root(root).unwrap();

        let config = WriteConfig {
            max_pending_ops: 2,
            ..Default::default()
        };

        let mut writer = BufferedWriter::new(root, "test", config).unwrap();

        writer.put("doc1", json!({"name": "alice"})).unwrap();
        writer.put("doc2", json!({"name": "bob"})).unwrap();
        // Should auto-flush after 2 ops

        // Verify files exist
        assert!(Layout::doc_file(root, "test", "doc1").exists());
        assert!(Layout::doc_file(root, "test", "doc2").exists());
    }

    #[test]
    fn test_sync_writer() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();
        Layout::init_root(root).unwrap();

        let mut writer = SyncWriter::new(root, "test").unwrap();

        writer.put("doc1", &json!({"name": "alice"})).unwrap();
        assert!(Layout::doc_file(root, "test", "doc1").exists());

        writer.delete("doc1").unwrap();
        assert!(!Layout::doc_file(root, "test", "doc1").exists());
    }
}
