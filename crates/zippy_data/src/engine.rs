//! Main engine for ZDS operations.

use std::path::Path;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    codec::{Codec, Predicate},
    container::ContainerFS,
    index::IndexRegistry,
    schema::SchemaRegistry,
    Error, Result,
};

/// Manifest for a collection.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Manifest {
    pub version: String,
    pub collection: String,
    pub strict: bool,
    pub created_at: String,
    pub doc_count: u64,
    pub schema_count: u64,
}

impl Manifest {
    pub fn new(collection: &str, strict: bool) -> Self {
        Manifest {
            version: crate::ZDS_VERSION.to_string(),
            collection: collection.to_string(),
            strict,
            created_at: chrono::Utc::now().to_rfc3339(),
            doc_count: 0,
            schema_count: 0,
        }
    }
}

/// Main ZDS engine.
pub struct Engine {
    container: ContainerFS,
    collection: String,
    index: IndexRegistry,
    schema_registry: SchemaRegistry,
}

impl Engine {
    /// Open an existing collection.
    pub fn open(container_path: impl AsRef<Path>, collection: impl AsRef<str>) -> Result<Self> {
        let container = ContainerFS::open(container_path)?;
        let collection = collection.as_ref().to_string();

        // Load indexes
        let index = if container.is_folder() {
            IndexRegistry::load(container.root_path(), &collection).unwrap_or_default()
        } else {
            // For zip archives, rebuild index from contents
            IndexRegistry::new() // TODO: implement zip index loading
        };

        let schema_registry = if container.is_folder() {
            SchemaRegistry::load(container.root_path(), &collection)
                .unwrap_or_else(|_| SchemaRegistry::new(false))
        } else {
            SchemaRegistry::new(false)
        };

        Ok(Engine {
            container,
            collection,
            index,
            schema_registry,
        })
    }

    /// Get a single document by ID.
    pub fn get_document(&self, doc_id: &str) -> Result<Value> {
        let relative_path = format!("collections/{}/docs/{}.json", self.collection, doc_id);
        let content = self.container.read_file_string(Path::new(&relative_path))?;
        Codec::decode(&content)
    }

    /// Get document at index position (based on order.ids).
    pub fn get_document_at(&self, index: usize) -> Result<Value> {
        let doc_id = self
            .index
            .get_doc_id_at(index)
            .ok_or_else(|| Error::DocumentNotFound(format!("index {}", index)))?;
        self.get_document(doc_id)
    }

    /// Create a scanner for iterating documents.
    pub fn scan(&self, predicate: Option<&Predicate>, fields: Option<&[&str]>) -> Result<Scanner> {
        Scanner::new(
            self.container.clone(),
            self.collection.clone(),
            self.index.clone(),
            predicate.cloned(),
            fields.map(|f| f.iter().map(|s| s.to_string()).collect()),
        )
    }

    /// Get collection statistics.
    pub fn stats(&self) -> CollectionStats {
        CollectionStats {
            collection: self.collection.clone(),
            doc_count: self.index.len(),
            schema_count: self.schema_registry.schema_count(),
            total_size: self.index.total_size(),
            strict_mode: self.schema_registry.is_strict(),
        }
    }

    /// Get all document IDs.
    pub fn doc_ids(&self) -> &[String] {
        self.index.all_doc_ids()
    }

    /// Get document count.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    /// Check if collection is empty.
    pub fn is_empty(&self) -> bool {
        self.index.is_empty()
    }

    /// Get the index registry.
    pub fn index(&self) -> &IndexRegistry {
        &self.index
    }

    /// Get the schema registry.
    pub fn schema_registry(&self) -> &SchemaRegistry {
        &self.schema_registry
    }

    /// Get the container.
    pub fn container(&self) -> &ContainerFS {
        &self.container
    }

    /// Rebuild indexes from disk.
    pub fn rebuild_index(&mut self) -> Result<()> {
        if self.container.is_folder() {
            self.index = IndexRegistry::rebuild(self.container.root_path(), &self.collection)?;
        }
        Ok(())
    }
}

/// Collection statistics.
#[derive(Debug, Clone)]
pub struct CollectionStats {
    pub collection: String,
    pub doc_count: usize,
    pub schema_count: usize,
    pub total_size: u64,
    pub strict_mode: bool,
}

/// Scanner for iterating over documents with optional filtering.
pub struct Scanner {
    container: ContainerFS,
    collection: String,
    doc_ids: Vec<String>,
    predicate: Option<Predicate>,
    fields: Option<Vec<String>>,
    current_idx: usize,
}

impl Scanner {
    fn new(
        container: ContainerFS,
        collection: String,
        index: IndexRegistry,
        predicate: Option<Predicate>,
        fields: Option<Vec<String>>,
    ) -> Result<Self> {
        let doc_ids = index.all_doc_ids().to_vec();
        Ok(Scanner {
            container,
            collection,
            doc_ids,
            predicate,
            fields,
            current_idx: 0,
        })
    }

    /// Get the next document matching the predicate.
    pub fn next_doc(&mut self) -> Result<Option<Value>> {
        while self.current_idx < self.doc_ids.len() {
            let doc_id = &self.doc_ids[self.current_idx].clone();
            self.current_idx += 1;

            let relative_path = format!("collections/{}/docs/{}.json", self.collection, doc_id);
            let content = match self.container.read_file_string(Path::new(&relative_path)) {
                Ok(c) => c,
                Err(_) => continue,
            };

            let doc = Codec::decode(&content)?;

            // Apply predicate
            if let Some(ref pred) = self.predicate {
                if !Codec::apply_predicate(&doc, pred)? {
                    continue;
                }
            }

            // Apply projection
            let result = if let Some(ref fields) = self.fields {
                let field_refs: Vec<&str> = fields.iter().map(|s| s.as_str()).collect();
                Codec::extract_fields(&doc, &field_refs)?
            } else {
                doc
            };

            return Ok(Some(result));
        }
        Ok(None)
    }

    /// Collect all remaining documents.
    pub fn collect(&mut self) -> Result<Vec<Value>> {
        let mut docs = Vec::new();
        while let Some(doc) = self.next_doc()? {
            docs.push(doc);
        }
        Ok(docs)
    }

    /// Reset scanner to beginning.
    pub fn reset(&mut self) {
        self.current_idx = 0;
    }

    /// Get remaining count (approximate, doesn't account for predicate).
    pub fn remaining(&self) -> usize {
        self.doc_ids.len().saturating_sub(self.current_idx)
    }
}

impl Iterator for Scanner {
    type Item = Result<Value>;

    fn next(&mut self) -> Option<Self::Item> {
        match self.next_doc() {
            Ok(Some(doc)) => Some(Ok(doc)),
            Ok(None) => None,
            Err(e) => Some(Err(e)),
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;
    use tempfile::TempDir;

    use super::*;
    use crate::{writer::SyncWriter, Layout};

    fn setup_test_collection() -> (TempDir, std::path::PathBuf) {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path().to_path_buf();
        Layout::init_root(&root).unwrap();

        let mut writer = SyncWriter::new(&root, "test").unwrap();
        writer
            .put("doc1", &json!({"name": "alice", "age": 30}))
            .unwrap();
        writer
            .put("doc2", &json!({"name": "bob", "age": 25}))
            .unwrap();
        writer
            .put("doc3", &json!({"name": "charlie", "age": 35}))
            .unwrap();

        (tmp, root)
    }

    #[test]
    fn test_engine_open_and_get() {
        let (_tmp, root) = setup_test_collection();

        let engine = Engine::open(&root, "test").unwrap();
        assert_eq!(engine.len(), 3);

        let doc = engine.get_document("doc1").unwrap();
        assert_eq!(doc["name"], "alice");
    }

    #[test]
    fn test_engine_scan() {
        let (_tmp, root) = setup_test_collection();

        let engine = Engine::open(&root, "test").unwrap();
        let scanner = engine.scan(None, None).unwrap();

        let docs: Vec<_> = scanner.collect();
        assert_eq!(docs.len(), 3);
    }

    #[test]
    fn test_engine_scan_with_predicate() {
        let (_tmp, root) = setup_test_collection();

        let engine = Engine::open(&root, "test").unwrap();
        let pred = Predicate::eq("name", "alice");
        let scanner = engine.scan(Some(&pred), None).unwrap();

        let docs: Vec<_> = scanner.collect();
        assert_eq!(docs.len(), 1);
        assert_eq!(docs[0].as_ref().unwrap()["name"], "alice");
    }

    #[test]
    fn test_engine_scan_with_projection() {
        let (_tmp, root) = setup_test_collection();

        let engine = Engine::open(&root, "test").unwrap();
        let scanner = engine.scan(None, Some(&["name"])).unwrap();

        let docs: Vec<_> = scanner.collect();
        assert_eq!(docs.len(), 3);
        // Should only have "name" field
        let doc = docs[0].as_ref().unwrap();
        assert!(doc.get("name").is_some());
        assert!(doc.get("age").is_none());
    }

    #[test]
    fn test_engine_stats() {
        let (_tmp, root) = setup_test_collection();

        let engine = Engine::open(&root, "test").unwrap();
        let stats = engine.stats();

        assert_eq!(stats.collection, "test");
        assert_eq!(stats.doc_count, 3);
        assert_eq!(stats.schema_count, 1); // All docs have same schema
    }
}
