//! Document index and ordering.

use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Write},
    path::Path,
};

use serde::{Deserialize, Serialize};

use crate::{Layout, Result};

/// Document index entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DocIndexEntry {
    pub doc_id: String,
    pub schema_id: String,
    pub size: u64,
    pub mtime: u64,
}

/// Index registry for a collection.
#[derive(Debug, Clone)]
pub struct IndexRegistry {
    /// Document index: doc_id -> entry
    doc_index: HashMap<String, DocIndexEntry>,
    /// Ordered list of document IDs (stable iteration order)
    order: Vec<String>,
}

impl IndexRegistry {
    /// Create a new empty index registry.
    pub fn new() -> Self {
        IndexRegistry {
            doc_index: HashMap::new(),
            order: Vec::new(),
        }
    }

    /// Load index from disk.
    pub fn load(root: &Path, collection: &str) -> Result<Self> {
        let mut registry = IndexRegistry::new();

        // Load doc_index.jsonl
        let index_path = Layout::doc_index(root, collection);
        if index_path.exists() {
            let file = std::fs::File::open(&index_path)?;
            let reader = BufReader::new(file);

            for line in reader.lines() {
                let line = line?;
                if line.trim().is_empty() {
                    continue;
                }
                let entry: DocIndexEntry = serde_json::from_str(&line)?;
                registry.doc_index.insert(entry.doc_id.clone(), entry);
            }
        }

        // Load order.ids
        let order_path = Layout::order_file(root, collection);
        if order_path.exists() {
            let content = std::fs::read_to_string(&order_path)?;
            for line in content.lines() {
                let doc_id = line.trim();
                if !doc_id.is_empty() {
                    registry.order.push(doc_id.to_string());
                }
            }
        } else {
            // Fallback: use doc_index keys in arbitrary order
            registry.order = registry.doc_index.keys().cloned().collect();
        }

        Ok(registry)
    }

    /// Save index to disk.
    pub fn save(&self, root: &Path, collection: &str) -> Result<()> {
        // Save doc_index.jsonl
        let index_path = Layout::doc_index(root, collection);
        let mut file = std::fs::File::create(&index_path)?;
        for entry in self.doc_index.values() {
            let line = serde_json::to_string(entry)?;
            writeln!(file, "{}", line)?;
        }

        // Save order.ids
        let order_path = Layout::order_file(root, collection);
        let mut file = std::fs::File::create(&order_path)?;
        for doc_id in &self.order {
            writeln!(file, "{}", doc_id)?;
        }

        Ok(())
    }

    /// Add or update a document in the index.
    pub fn put(&mut self, entry: DocIndexEntry) {
        let doc_id = entry.doc_id.clone();
        let is_new = !self.doc_index.contains_key(&doc_id);
        self.doc_index.insert(doc_id.clone(), entry);
        if is_new {
            self.order.push(doc_id);
        }
    }

    /// Remove a document from the index.
    pub fn remove(&mut self, doc_id: &str) -> Option<DocIndexEntry> {
        self.order.retain(|id| id != doc_id);
        self.doc_index.remove(doc_id)
    }

    /// Get a document index entry.
    pub fn get(&self, doc_id: &str) -> Option<&DocIndexEntry> {
        self.doc_index.get(doc_id)
    }

    /// Check if document exists.
    pub fn contains(&self, doc_id: &str) -> bool {
        self.doc_index.contains_key(doc_id)
    }

    /// Get all document IDs in order.
    pub fn all_doc_ids(&self) -> &[String] {
        &self.order
    }

    /// Get document ID at index position.
    pub fn get_doc_id_at(&self, index: usize) -> Option<&str> {
        self.order.get(index).map(|s| s.as_str())
    }

    /// Get document count.
    pub fn len(&self) -> usize {
        self.doc_index.len()
    }

    /// Check if empty.
    pub fn is_empty(&self) -> bool {
        self.doc_index.is_empty()
    }

    /// Get total size of all documents.
    pub fn total_size(&self) -> u64 {
        self.doc_index.values().map(|e| e.size).sum()
    }

    /// Iterate over all entries.
    pub fn iter(&self) -> impl Iterator<Item = &DocIndexEntry> {
        self.order.iter().filter_map(|id| self.doc_index.get(id))
    }

    /// Rebuild index from disk by scanning docs directory.
    pub fn rebuild(root: &Path, collection: &str) -> Result<Self> {
        let docs_dir = Layout::docs_dir(root, collection);
        let mut registry = IndexRegistry::new();

        if !docs_dir.exists() {
            return Ok(registry);
        }

        let mut entries: Vec<(String, DocIndexEntry)> = Vec::new();

        for entry in std::fs::read_dir(&docs_dir)? {
            let entry = entry?;
            let path = entry.path();

            if path.extension().map(|e| e == "json").unwrap_or(false) {
                let doc_id = path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("")
                    .to_string();

                if doc_id.is_empty() {
                    continue;
                }

                let metadata = std::fs::metadata(&path)?;
                let content = std::fs::read_to_string(&path)?;
                let doc: serde_json::Value = serde_json::from_str(&content)?;
                let schema_id = crate::schema::SchemaRegistry::compute_schema_id(&doc);

                let mtime = metadata
                    .modified()
                    .ok()
                    .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                    .map(|d| d.as_secs())
                    .unwrap_or(0);

                entries.push((
                    doc_id.clone(),
                    DocIndexEntry {
                        doc_id,
                        schema_id,
                        size: metadata.len(),
                        mtime,
                    },
                ));
            }
        }

        // Sort by doc_id for deterministic order when rebuilding
        entries.sort_by(|a, b| a.0.cmp(&b.0));

        for (_, entry) in entries {
            registry.put(entry);
        }

        Ok(registry)
    }
}

impl Default for IndexRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_index_operations() {
        let mut registry = IndexRegistry::new();

        let entry = DocIndexEntry {
            doc_id: "doc001".to_string(),
            schema_id: "abc123".to_string(),
            size: 100,
            mtime: 1699000000,
        };

        registry.put(entry.clone());
        assert_eq!(registry.len(), 1);
        assert!(registry.contains("doc001"));
        assert_eq!(registry.get("doc001").unwrap().size, 100);

        registry.remove("doc001");
        assert!(registry.is_empty());
    }

    #[test]
    fn test_order_preservation() {
        let mut registry = IndexRegistry::new();

        for i in 0..5 {
            registry.put(DocIndexEntry {
                doc_id: format!("doc{:03}", i),
                schema_id: "schema".to_string(),
                size: 100,
                mtime: 0,
            });
        }

        let ids: Vec<_> = registry.all_doc_ids().to_vec();
        assert_eq!(ids, vec!["doc000", "doc001", "doc002", "doc003", "doc004"]);
    }
}
