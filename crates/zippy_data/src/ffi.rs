//! C FFI for libzippy_data.
//!
//! Provides a stable C ABI for bindings (Python, Node, DuckDB).

use std::{
    ffi::{c_char, CStr, CString},
    ptr,
};

use crate::{Engine, Error};

/// Opaque handle to a ZDS engine.
pub struct ZdsEngine(Engine);

/// Error codes returned by FFI functions.
#[repr(C)]
#[allow(dead_code)]
pub enum ZdsError {
    Ok = 0,
    InvalidPath = 1,
    CollectionNotFound = 2,
    DocumentNotFound = 3,
    IoError = 4,
    JsonError = 5,
    SchemaMismatch = 6,
    Unknown = 99,
}

impl From<&Error> for ZdsError {
    fn from(e: &Error) -> Self {
        match e {
            Error::InvalidContainer(_) => ZdsError::InvalidPath,
            Error::CollectionNotFound(_) => ZdsError::CollectionNotFound,
            Error::DocumentNotFound(_) => ZdsError::DocumentNotFound,
            Error::Io(_) => ZdsError::IoError,
            Error::Json(_) => ZdsError::JsonError,
            Error::SchemaMismatch { .. } => ZdsError::SchemaMismatch,
            _ => ZdsError::Unknown,
        }
    }
}

/// Open a ZDS container and collection.
///
/// # Safety
/// - `path` must be a valid null-terminated C string
/// - `collection` must be a valid null-terminated C string
/// - Returns null on error
#[no_mangle]
pub unsafe extern "C" fn zds_open(
    path: *const c_char,
    collection: *const c_char,
) -> *mut ZdsEngine {
    if path.is_null() || collection.is_null() {
        return ptr::null_mut();
    }

    let path = match CStr::from_ptr(path).to_str() {
        Ok(s) => s,
        Err(_) => return ptr::null_mut(),
    };

    let collection = match CStr::from_ptr(collection).to_str() {
        Ok(s) => s,
        Err(_) => return ptr::null_mut(),
    };

    match Engine::open(path, collection) {
        Ok(engine) => Box::into_raw(Box::new(ZdsEngine(engine))),
        Err(_) => ptr::null_mut(),
    }
}

/// Close a ZDS engine handle.
///
/// # Safety
/// - `engine` must be a valid pointer returned by `zds_open`
/// - `engine` must not be used after this call
#[no_mangle]
pub unsafe extern "C" fn zds_close(engine: *mut ZdsEngine) {
    if !engine.is_null() {
        drop(Box::from_raw(engine));
    }
}

/// Get document count.
///
/// # Safety
/// - `engine` must be a valid pointer returned by `zds_open`
#[no_mangle]
pub unsafe extern "C" fn zds_count(engine: *const ZdsEngine) -> usize {
    if engine.is_null() {
        return 0;
    }
    (*engine).0.len()
}

/// Get a document by ID.
///
/// # Safety
/// - `engine` must be a valid pointer returned by `zds_open`
/// - `doc_id` must be a valid null-terminated C string
/// - Returns a newly allocated JSON string (caller must free with `zds_free_string`)
/// - Returns null on error
#[no_mangle]
pub unsafe extern "C" fn zds_get(engine: *const ZdsEngine, doc_id: *const c_char) -> *mut c_char {
    if engine.is_null() || doc_id.is_null() {
        return ptr::null_mut();
    }

    let doc_id = match CStr::from_ptr(doc_id).to_str() {
        Ok(s) => s,
        Err(_) => return ptr::null_mut(),
    };

    match (*engine).0.get_document(doc_id) {
        Ok(doc) => {
            let json = serde_json::to_string(&doc).unwrap_or_default();
            CString::new(json)
                .map(|s| s.into_raw())
                .unwrap_or(ptr::null_mut())
        }
        Err(_) => ptr::null_mut(),
    }
}

/// Get a document at index position.
///
/// # Safety
/// - `engine` must be a valid pointer returned by `zds_open`
/// - Returns a newly allocated JSON string (caller must free with `zds_free_string`)
/// - Returns null on error
#[no_mangle]
pub unsafe extern "C" fn zds_get_at(engine: *const ZdsEngine, index: usize) -> *mut c_char {
    if engine.is_null() {
        return ptr::null_mut();
    }

    match (*engine).0.get_document_at(index) {
        Ok(doc) => {
            let json = serde_json::to_string(&doc).unwrap_or_default();
            CString::new(json)
                .map(|s| s.into_raw())
                .unwrap_or(ptr::null_mut())
        }
        Err(_) => ptr::null_mut(),
    }
}

/// Free a string returned by ZDS functions.
///
/// # Safety
/// - `s` must be a pointer returned by a ZDS function or null
#[no_mangle]
pub unsafe extern "C" fn zds_free_string(s: *mut c_char) {
    if !s.is_null() {
        drop(CString::from_raw(s));
    }
}

/// Get all document IDs as a JSON array.
///
/// # Safety
/// - `engine` must be a valid pointer returned by `zds_open`
/// - Returns a newly allocated JSON array string (caller must free with `zds_free_string`)
#[no_mangle]
pub unsafe extern "C" fn zds_doc_ids(engine: *const ZdsEngine) -> *mut c_char {
    if engine.is_null() {
        return ptr::null_mut();
    }

    let ids = (*engine).0.doc_ids();
    let json = serde_json::to_string(ids).unwrap_or_else(|_| "[]".to_string());
    CString::new(json)
        .map(|s| s.into_raw())
        .unwrap_or(ptr::null_mut())
}

/// Scanner handle for iteration.
pub struct ZdsScanner(crate::Scanner);

/// Create a scanner for iterating documents.
///
/// # Safety
/// - `engine` must be a valid pointer returned by `zds_open`
/// - Returns null on error
#[no_mangle]
pub unsafe extern "C" fn zds_scan(engine: *const ZdsEngine) -> *mut ZdsScanner {
    if engine.is_null() {
        return ptr::null_mut();
    }

    match (*engine).0.scan(None, None) {
        Ok(scanner) => Box::into_raw(Box::new(ZdsScanner(scanner))),
        Err(_) => ptr::null_mut(),
    }
}

/// Get next document from scanner.
///
/// # Safety
/// - `scanner` must be a valid pointer returned by `zds_scan`
/// - Returns a newly allocated JSON string (caller must free with `zds_free_string`)
/// - Returns null when no more documents
#[no_mangle]
pub unsafe extern "C" fn zds_scan_next(scanner: *mut ZdsScanner) -> *mut c_char {
    if scanner.is_null() {
        return ptr::null_mut();
    }

    match (*scanner).0.next_doc() {
        Ok(Some(doc)) => {
            let json = serde_json::to_string(&doc).unwrap_or_default();
            CString::new(json)
                .map(|s| s.into_raw())
                .unwrap_or(ptr::null_mut())
        }
        Ok(None) => ptr::null_mut(),
        _ => ptr::null_mut(),
    }
}

/// Close a scanner handle.
///
/// # Safety
/// - `scanner` must be a valid pointer returned by `zds_scan`
#[no_mangle]
pub unsafe extern "C" fn zds_scan_close(scanner: *mut ZdsScanner) {
    if !scanner.is_null() {
        drop(Box::from_raw(scanner));
    }
}

/// Get ZDS library version.
///
/// # Safety
/// - Returns a static string, do not free
#[no_mangle]
pub extern "C" fn zds_version() -> *const c_char {
    static VERSION: &[u8] = b"0.1.0\0";
    VERSION.as_ptr() as *const c_char
}

#[cfg(test)]
mod tests {
    use serde_json::json;
    use tempfile::TempDir;

    use super::*;
    use crate::{writer::SyncWriter, Layout};

    #[test]
    fn test_ffi_basic() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();
        Layout::init_root(root).unwrap();

        let mut writer = SyncWriter::new(root, "test").unwrap();
        writer.put("doc1", &json!({"name": "alice"})).unwrap();

        unsafe {
            let path = CString::new(root.to_str().unwrap()).unwrap();
            let collection = CString::new("test").unwrap();

            let engine = zds_open(path.as_ptr(), collection.as_ptr());
            assert!(!engine.is_null());

            assert_eq!(zds_count(engine), 1);

            let doc_id = CString::new("doc1").unwrap();
            let json = zds_get(engine, doc_id.as_ptr());
            assert!(!json.is_null());
            let json_str = CStr::from_ptr(json).to_str().unwrap();
            assert!(json_str.contains("alice"));
            zds_free_string(json);

            zds_close(engine);
        }
    }
}
