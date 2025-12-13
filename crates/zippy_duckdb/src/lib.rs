//! DuckDB extension for ZDS (Zippy Data System)
//!
//! Provides `read_zds(path, collection, ...)` table function.
//!
//! # Implementation Notes
//!
//! DuckDB extensions require implementing:
//! - `duckdb_init`: Extension initialization
//! - `duckdb_version`: Version compatibility check
//!
//! Table functions require:
//! - `bind`: Parse parameters and determine output schema
//! - `init`: Initialize scan state
//! - `main`: Produce output tuples
//!
//! This is a stub implementation. Full implementation requires linking
//! against DuckDB's C API headers.

use zippy_core::{Engine, Scanner};
use std::ffi::{c_char, c_void};

/// Extension version (must match DuckDB version for compatibility).
pub const EXTENSION_VERSION: &str = "0.1.0";

/// Bind data for read_zds table function.
#[repr(C)]
pub struct ReadZdsBindData {
    pub path: *const c_char,
    pub collection: *const c_char,
    pub fields: *const *const c_char,
    pub field_count: usize,
}

/// Init data for read_zds table function.
#[repr(C)]
pub struct ReadZdsInitData {
    pub engine: *mut c_void,
    pub scanner: *mut c_void,
}

/// Global state for the extension.
pub struct ReadZdsGlobalState {
    pub engine: Option<Engine>,
}

/// Local state per thread/partition.
pub struct ReadZdsLocalState {
    pub scanner: Option<Scanner>,
    pub done: bool,
}

// ============================================================================
// DuckDB Extension Entry Points (stubs)
// ============================================================================

/// Extension initialization entry point.
///
/// Called when the extension is loaded. Should register table functions.
#[no_mangle]
pub extern "C" fn duckdb_init(_db: *mut c_void) {
    // TODO: Register read_zds table function
    // duckdb_register_table_function(db, create_read_zds_function());
}

/// Version check entry point.
///
/// DuckDB calls this to verify extension compatibility.
#[no_mangle]
pub extern "C" fn duckdb_version() -> *const c_char {
    static VERSION: &[u8] = b"v0.9.0\0";
    VERSION.as_ptr() as *const c_char
}

// ============================================================================
// Table Function Implementation (stubs)
// ============================================================================

/// Bind function: parse parameters and determine output schema.
///
/// # Parameters
/// - `info`: DuckDB bind info handle
///
/// # Expected SQL
/// ```sql
/// SELECT * FROM read_zds('path/to/store', 'collection_name')
/// SELECT name, age FROM read_zds('path/to/store', 'collection_name')
/// ```
#[no_mangle]
pub extern "C" fn read_zds_bind(_info: *mut c_void) {
    // TODO: Implement bind logic
    // 1. Parse path and collection parameters
    // 2. Open Engine to get schema info
    // 3. Set output column names and types based on schema
    // 4. Store bind data for init/main
}

/// Init function: initialize scan state.
///
/// Called once per thread/partition before scanning.
#[no_mangle]
pub extern "C" fn read_zds_init(_info: *mut c_void) {
    // TODO: Implement init logic
    // 1. Get bind data (path, collection, projection)
    // 2. Create Engine and Scanner
    // 3. Store in init data
}

/// Main function: produce output tuples.
///
/// Called repeatedly to fetch rows.
#[no_mangle]
pub extern "C" fn read_zds_main(_info: *mut c_void, _output: *mut c_void) {
    // TODO: Implement main logic
    // 1. Get scanner from local state
    // 2. Fetch batch of documents
    // 3. Convert to DuckDB vectors
    // 4. Set cardinality
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Convert JSON value to appropriate DuckDB type.
fn json_to_duckdb_type(value: &serde_json::Value) -> &'static str {
    match value {
        serde_json::Value::Null => "VARCHAR",
        serde_json::Value::Bool(_) => "BOOLEAN",
        serde_json::Value::Number(n) => {
            if n.is_i64() {
                "BIGINT"
            } else {
                "DOUBLE"
            }
        }
        serde_json::Value::String(_) => "VARCHAR",
        serde_json::Value::Array(_) => "JSON",
        serde_json::Value::Object(_) => "JSON",
    }
}

/// Infer DuckDB schema from ZDS schema.
pub fn infer_schema(engine: &Engine) -> Vec<(&'static str, &'static str)> {
    // Get first document to infer types
    if let Ok(doc) = engine.get_document_at(0) {
        if let Some(obj) = doc.as_object() {
            return obj
                .iter()
                .map(|(k, v)| {
                    let key: &'static str = Box::leak(k.clone().into_boxed_str());
                    (key, json_to_duckdb_type(v))
                })
                .collect();
        }
    }
    Vec::new()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_json_type_mapping() {
        assert_eq!(json_to_duckdb_type(&serde_json::json!(null)), "VARCHAR");
        assert_eq!(json_to_duckdb_type(&serde_json::json!(true)), "BOOLEAN");
        assert_eq!(json_to_duckdb_type(&serde_json::json!(42)), "BIGINT");
        assert_eq!(json_to_duckdb_type(&serde_json::json!(3.14)), "DOUBLE");
        assert_eq!(json_to_duckdb_type(&serde_json::json!("hello")), "VARCHAR");
        assert_eq!(json_to_duckdb_type(&serde_json::json!([1, 2, 3])), "JSON");
        assert_eq!(json_to_duckdb_type(&serde_json::json!({"a": 1})), "JSON");
    }
}
