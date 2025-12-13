//! JSON codec with projection and predicate support.

use serde_json::{Map, Value};

use crate::{Error, Result};

/// Predicate for filtering documents during scan.
#[derive(Debug, Clone)]
pub enum Predicate {
    /// Field equals value
    Eq(String, Value),
    /// Field exists
    Exists(String),
    /// Field does not exist
    NotExists(String),
    /// Logical AND of predicates
    And(Vec<Predicate>),
    /// Logical OR of predicates
    Or(Vec<Predicate>),
}

impl Predicate {
    /// Create an equality predicate.
    pub fn eq(field: impl Into<String>, value: impl Into<Value>) -> Self {
        Predicate::Eq(field.into(), value.into())
    }

    /// Create an exists predicate.
    pub fn exists(field: impl Into<String>) -> Self {
        Predicate::Exists(field.into())
    }

    /// Combine predicates with AND.
    pub fn and(predicates: Vec<Predicate>) -> Self {
        Predicate::And(predicates)
    }

    /// Combine predicates with OR.
    pub fn or(predicates: Vec<Predicate>) -> Self {
        Predicate::Or(predicates)
    }
}

/// JSON codec for ZDS documents.
pub struct Codec;

impl Codec {
    /// Decode JSON string to Value.
    pub fn decode(s: &str) -> Result<Value> {
        serde_json::from_str(s).map_err(Error::from)
    }

    /// Encode Value to JSON string.
    pub fn encode(v: &Value) -> Result<String> {
        serde_json::to_string(v).map_err(Error::from)
    }

    /// Encode Value to pretty JSON string.
    pub fn encode_pretty(v: &Value) -> Result<String> {
        serde_json::to_string_pretty(v).map_err(Error::from)
    }

    /// Extract specified fields from a document (projection).
    pub fn extract_fields(doc: &Value, fields: &[&str]) -> Result<Value> {
        let _obj = doc
            .as_object()
            .ok_or_else(|| Error::Codec("Cannot extract fields from non-object".to_string()))?;

        let mut result = Map::new();
        for field in fields {
            // Support nested field access with dot notation
            if let Some(value) = Self::get_nested(doc, field) {
                // For nested fields, use the leaf name as key
                let key = field.rsplit('.').next().unwrap_or(field);
                result.insert(key.to_string(), value.clone());
            }
        }

        Ok(Value::Object(result))
    }

    /// Get a nested field value using dot notation.
    fn get_nested<'a>(doc: &'a Value, path: &str) -> Option<&'a Value> {
        let parts: Vec<&str> = path.split('.').collect();
        let mut current = doc;

        for part in parts {
            current = current.get(part)?;
        }

        Some(current)
    }

    /// Apply a predicate to a document.
    pub fn apply_predicate(doc: &Value, pred: &Predicate) -> Result<bool> {
        match pred {
            Predicate::Eq(field, expected) => {
                let actual = Self::get_nested(doc, field);
                Ok(actual == Some(expected))
            }
            Predicate::Exists(field) => Ok(Self::get_nested(doc, field).is_some()),
            Predicate::NotExists(field) => Ok(Self::get_nested(doc, field).is_none()),
            Predicate::And(preds) => {
                for p in preds {
                    if !Self::apply_predicate(doc, p)? {
                        return Ok(false);
                    }
                }
                Ok(true)
            }
            Predicate::Or(preds) => {
                for p in preds {
                    if Self::apply_predicate(doc, p)? {
                        return Ok(true);
                    }
                }
                Ok(false)
            }
        }
    }

    /// Canonicalize a JSON value for schema hashing.
    /// Sorts object keys recursively and produces deterministic output.
    pub fn canonicalize(v: &Value) -> String {
        match v {
            Value::Object(map) => {
                let mut pairs: Vec<_> = map
                    .iter()
                    .map(|(k, v)| format!("\"{}\":{}", k, Self::canonicalize(v)))
                    .collect();
                pairs.sort();
                format!("{{{}}}", pairs.join(","))
            }
            Value::Array(arr) => {
                let items: Vec<_> = arr.iter().map(Self::canonicalize).collect();
                format!("[{}]", items.join(","))
            }
            _ => v.to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn test_decode_encode() {
        let s = r#"{"name": "test", "value": 42}"#;
        let v = Codec::decode(s).unwrap();
        assert_eq!(v["name"], "test");
        assert_eq!(v["value"], 42);
    }

    #[test]
    fn test_extract_fields() {
        let doc = json!({"name": "test", "value": 42, "extra": "ignored"});
        let result = Codec::extract_fields(&doc, &["name", "value"]).unwrap();
        assert_eq!(result["name"], "test");
        assert_eq!(result["value"], 42);
        assert!(result.get("extra").is_none());
    }

    #[test]
    fn test_nested_field_access() {
        let doc = json!({"user": {"name": "alice", "age": 30}});
        let result = Codec::extract_fields(&doc, &["user.name"]).unwrap();
        assert_eq!(result["name"], "alice");
    }

    #[test]
    fn test_predicate_eq() {
        let doc = json!({"status": "active", "count": 5});

        let pred = Predicate::eq("status", "active");
        assert!(Codec::apply_predicate(&doc, &pred).unwrap());

        let pred = Predicate::eq("status", "inactive");
        assert!(!Codec::apply_predicate(&doc, &pred).unwrap());
    }

    #[test]
    fn test_predicate_exists() {
        let doc = json!({"name": "test"});

        assert!(Codec::apply_predicate(&doc, &Predicate::exists("name")).unwrap());
        assert!(!Codec::apply_predicate(&doc, &Predicate::exists("missing")).unwrap());
    }

    #[test]
    fn test_predicate_and_or() {
        let doc = json!({"a": 1, "b": 2});

        let pred = Predicate::and(vec![Predicate::eq("a", 1), Predicate::eq("b", 2)]);
        assert!(Codec::apply_predicate(&doc, &pred).unwrap());

        let pred = Predicate::or(vec![Predicate::eq("a", 99), Predicate::eq("b", 2)]);
        assert!(Codec::apply_predicate(&doc, &pred).unwrap());
    }

    #[test]
    fn test_canonicalize() {
        let v1 = json!({"b": 2, "a": 1});
        let v2 = json!({"a": 1, "b": 2});
        assert_eq!(Codec::canonicalize(&v1), Codec::canonicalize(&v2));
    }
}
