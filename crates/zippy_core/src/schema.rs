//! Schema registry and schema identity computation.

use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Write},
    path::Path,
};

use blake3;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{Codec, Error, Layout, Result};

/// A schema entry in the registry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchemaEntry {
    pub schema_id: String,
    pub schema: Value,
    pub count: u64,
}

/// Schema registry for a collection.
#[derive(Debug, Clone)]
pub struct SchemaRegistry {
    /// Map from schema_id to schema entry
    schemas: HashMap<String, SchemaEntry>,
    /// Whether this collection is in strict mode
    strict: bool,
    /// The required schema_id in strict mode
    strict_schema_id: Option<String>,
}

impl SchemaRegistry {
    /// Create a new empty schema registry.
    pub fn new(strict: bool) -> Self {
        SchemaRegistry {
            schemas: HashMap::new(),
            strict,
            strict_schema_id: None,
        }
    }

    /// Load schema registry from disk.
    pub fn load(root: &Path, collection: &str) -> Result<Self> {
        let path = Layout::schema_registry(root, collection);
        let manifest_path = Layout::manifest_file(root, collection);

        // Read strict mode from manifest if it exists
        let strict = if manifest_path.exists() {
            let content = std::fs::read_to_string(&manifest_path)?;
            let manifest: Value = serde_json::from_str(&content)?;
            manifest
                .get("strict")
                .and_then(|v| v.as_bool())
                .unwrap_or(false)
        } else {
            false
        };

        let mut registry = SchemaRegistry::new(strict);

        if path.exists() {
            let file = std::fs::File::open(&path)?;
            let reader = BufReader::new(file);

            for line in reader.lines() {
                let line = line?;
                if line.trim().is_empty() {
                    continue;
                }
                let entry: SchemaEntry = serde_json::from_str(&line)?;
                if registry.strict && registry.strict_schema_id.is_none() {
                    registry.strict_schema_id = Some(entry.schema_id.clone());
                }
                registry.schemas.insert(entry.schema_id.clone(), entry);
            }
        }

        Ok(registry)
    }

    /// Save schema registry to disk.
    pub fn save(&self, root: &Path, collection: &str) -> Result<()> {
        let path = Layout::schema_registry(root, collection);
        let mut file = std::fs::File::create(&path)?;

        for entry in self.schemas.values() {
            let line = serde_json::to_string(entry)?;
            writeln!(file, "{}", line)?;
        }

        Ok(())
    }

    /// Compute schema ID for a document.
    pub fn compute_schema_id(doc: &Value) -> String {
        let schema = Self::extract_schema(doc);
        let canonical = Codec::canonicalize(&schema);
        let hash = blake3::hash(canonical.as_bytes());
        hash.to_hex().to_string()
    }

    /// Extract structural schema from a document (types, not values).
    pub fn extract_schema(doc: &Value) -> Value {
        match doc {
            Value::Object(map) => {
                let mut schema_map = serde_json::Map::new();
                for (k, v) in map {
                    schema_map.insert(k.clone(), Self::extract_schema(v));
                }
                Value::Object(schema_map)
            }
            Value::Array(arr) => {
                // For arrays, use schema of first element (if any)
                if let Some(first) = arr.first() {
                    Value::Array(vec![Self::extract_schema(first)])
                } else {
                    Value::Array(vec![])
                }
            }
            Value::String(_) => Value::String("string".to_string()),
            Value::Number(n) => {
                if n.is_i64() {
                    Value::String("integer".to_string())
                } else {
                    Value::String("number".to_string())
                }
            }
            Value::Bool(_) => Value::String("boolean".to_string()),
            Value::Null => Value::String("null".to_string()),
        }
    }

    /// Register a document and return its schema ID.
    /// In strict mode, fails if schema doesn't match.
    pub fn register(&mut self, doc: &Value) -> Result<String> {
        let schema_id = Self::compute_schema_id(doc);

        if self.strict {
            if let Some(ref expected) = self.strict_schema_id {
                if &schema_id != expected {
                    return Err(Error::SchemaMismatch {
                        expected: expected.clone(),
                        actual: schema_id,
                    });
                }
            } else {
                // First document sets the schema
                self.strict_schema_id = Some(schema_id.clone());
            }
        }

        if let Some(entry) = self.schemas.get_mut(&schema_id) {
            entry.count += 1;
        } else {
            let schema = Self::extract_schema(doc);
            self.schemas.insert(
                schema_id.clone(),
                SchemaEntry {
                    schema_id: schema_id.clone(),
                    schema,
                    count: 1,
                },
            );
        }

        Ok(schema_id)
    }

    /// Decrement count for a schema (when deleting a document).
    pub fn unregister(&mut self, schema_id: &str) {
        if let Some(entry) = self.schemas.get_mut(schema_id) {
            entry.count = entry.count.saturating_sub(1);
            // Optionally remove schema if count reaches 0
            // For now, keep it for historical tracking
        }
    }

    /// Get all schemas.
    pub fn schemas(&self) -> impl Iterator<Item = &SchemaEntry> {
        self.schemas.values()
    }

    /// Get schema by ID.
    pub fn get(&self, schema_id: &str) -> Option<&SchemaEntry> {
        self.schemas.get(schema_id)
    }

    /// Check if in strict mode.
    pub fn is_strict(&self) -> bool {
        self.strict
    }

    /// Get the strict schema ID (if in strict mode and schema is set).
    pub fn strict_schema_id(&self) -> Option<&str> {
        self.strict_schema_id.as_deref()
    }

    /// Get count of unique schemas.
    pub fn schema_count(&self) -> usize {
        self.schemas.len()
    }

    /// Get total document count across all schemas.
    pub fn total_doc_count(&self) -> u64 {
        self.schemas.values().map(|e| e.count).sum()
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn test_compute_schema_id() {
        let doc1 = json!({"name": "alice", "age": 30});
        let doc2 = json!({"name": "bob", "age": 25});
        let doc3 = json!({"name": "charlie"}); // Different schema

        let id1 = SchemaRegistry::compute_schema_id(&doc1);
        let id2 = SchemaRegistry::compute_schema_id(&doc2);
        let id3 = SchemaRegistry::compute_schema_id(&doc3);

        // Same structure = same schema ID
        assert_eq!(id1, id2);
        // Different structure = different schema ID
        assert_ne!(id1, id3);
    }

    #[test]
    fn test_extract_schema() {
        let doc = json!({
            "name": "alice",
            "age": 30,
            "active": true,
            "tags": ["a", "b"],
            "meta": {"x": 1}
        });

        let schema = SchemaRegistry::extract_schema(&doc);
        assert_eq!(schema["name"], "string");
        assert_eq!(schema["age"], "integer");
        assert_eq!(schema["active"], "boolean");
    }

    #[test]
    fn test_flexible_mode() {
        let mut registry = SchemaRegistry::new(false);

        let doc1 = json!({"a": 1});
        let doc2 = json!({"b": 2});

        // Both should succeed in flexible mode
        registry.register(&doc1).unwrap();
        registry.register(&doc2).unwrap();

        assert_eq!(registry.schema_count(), 2);
    }

    #[test]
    fn test_strict_mode() {
        let mut registry = SchemaRegistry::new(true);

        let doc1 = json!({"name": "alice"});
        let doc2 = json!({"name": "bob"});
        let doc3 = json!({"different": "schema"});

        // First document sets the schema
        registry.register(&doc1).unwrap();
        // Same schema succeeds
        registry.register(&doc2).unwrap();
        // Different schema fails
        assert!(registry.register(&doc3).is_err());
    }
}
