#![allow(clippy::useless_conversion)] // PyO3-generated wrappers trigger this lint

//! Python bindings for ZDS using PyO3.

use std::sync::Mutex;

use pyo3::{
    exceptions::{PyIOError, PyKeyError, PyValueError},
    prelude::*,
    types::{PyDict, PyList, PyTuple},
};
use zippy_data::FastStore;

/// Convert serde_json::Value to Python object
fn json_to_py(py: Python<'_>, value: &serde_json::Value) -> PyResult<PyObject> {
    match value {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(b) => Ok(b.to_object(py)),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.to_object(py))
            } else if let Some(f) = n.as_f64() {
                Ok(f.to_object(py))
            } else {
                Err(PyValueError::new_err("Invalid number"))
            }
        }
        serde_json::Value::String(s) => Ok(s.to_object(py)),
        serde_json::Value::Array(arr) => {
            let list = PyList::empty_bound(py);
            for item in arr {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.into())
        }
        serde_json::Value::Object(obj) => {
            let dict = PyDict::new_bound(py);
            for (k, v) in obj {
                dict.set_item(k, json_to_py(py, v)?)?;
            }
            Ok(dict.into())
        }
    }
}

/// Convert Python object to serde_json::Value
fn py_to_json(obj: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if obj.is_none() {
        return Ok(serde_json::Value::Null);
    }

    if let Ok(b) = obj.extract::<bool>() {
        return Ok(serde_json::Value::Bool(b));
    }

    if let Ok(i) = obj.extract::<i64>() {
        return Ok(serde_json::Value::Number(i.into()));
    }

    if let Ok(f) = obj.extract::<f64>() {
        if let Some(n) = serde_json::Number::from_f64(f) {
            return Ok(serde_json::Value::Number(n));
        }
    }

    if let Ok(s) = obj.extract::<String>() {
        return Ok(serde_json::Value::String(s));
    }

    if let Ok(list) = obj.downcast::<PyList>() {
        let mut arr = Vec::new();
        for item in list.iter() {
            arr.push(py_to_json(&item)?);
        }
        return Ok(serde_json::Value::Array(arr));
    }

    if let Ok(dict) = obj.downcast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            let key = k.extract::<String>()?;
            map.insert(key, py_to_json(&v)?);
        }
        return Ok(serde_json::Value::Object(map));
    }

    Err(PyValueError::new_err(format!(
        "Cannot convert {} to JSON",
        obj.get_type().name()?
    )))
}

/// High-performance ZDS Store backed by Rust FastStore (JSONL-based).
#[pyclass]
pub struct NativeStore {
    store: Mutex<FastStore>,
    root: String,
    collection: String,
}

#[allow(clippy::useless_conversion)]
#[pymethods]
impl NativeStore {
    /// Open a ZDS store.
    #[staticmethod]
    #[pyo3(signature = (root, collection = "default", batch_size = 5000))]
    fn open(root: String, collection: &str, batch_size: usize) -> PyResult<Self> {
        let store = FastStore::open(&root, collection, batch_size)
            .map_err(|e| PyIOError::new_err(format!("Failed to open store: {}", e)))?;

        Ok(NativeStore {
            store: Mutex::new(store),
            root,
            collection: collection.to_string(),
        })
    }

    /// Get document by ID.
    fn get(&self, py: Python<'_>, doc_id: &str) -> PyResult<PyObject> {
        let store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        let value = store
            .get(doc_id)
            .map_err(|_| PyKeyError::new_err(format!("Document not found: {}", doc_id)))?;
        json_to_py(py, &value)
    }

    /// Put a document.
    fn put(&self, doc_id: &str, doc: &Bound<'_, PyDict>) -> PyResult<()> {
        let value = py_to_json(doc.as_any())?;
        let mut store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        store
            .put(doc_id, value)
            .map_err(|e| PyIOError::new_err(format!("Write failed: {}", e)))?;
        Ok(())
    }

    /// Put multiple documents in a single batch (much faster than individual puts).
    fn put_batch(&self, items: &Bound<'_, PyList>) -> PyResult<usize> {
        // Convert all items first (outside the lock)
        let mut batch: Vec<(String, serde_json::Value)> = Vec::with_capacity(items.len());
        for item in items.iter() {
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyValueError::new_err("Expected list of (doc_id, doc) tuples"))?;
            if tuple.len() != 2 {
                return Err(PyValueError::new_err(
                    "Each item must be a (doc_id, doc) tuple",
                ));
            }
            let doc_id: String = tuple.get_item(0)?.extract()?;
            let doc = py_to_json(&tuple.get_item(1)?)?;
            batch.push((doc_id, doc));
        }

        // Now acquire lock once and write all
        let mut store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;

        let count = batch.len();
        for (doc_id, doc) in batch {
            store
                .put(doc_id, doc)
                .map_err(|e| PyIOError::new_err(format!("Write failed: {}", e)))?;
        }

        Ok(count)
    }

    /// Put multiple documents as raw JSONL bytes (fastest path - zero parsing).
    /// Each line must be valid JSON with "_id" field included.
    /// Use with orjson:
    ///   lines = [orjson.dumps({"_id": id, **doc}) for id, doc in items]
    ///   store.put_raw_batch([(id, line) for (id, _), line in zip(items, lines)])
    fn put_raw_batch(&self, items: &Bound<'_, PyList>) -> PyResult<usize> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;

        let mut count = 0;
        for item in items.iter() {
            let tuple = item.downcast::<PyTuple>().map_err(|_| {
                PyValueError::new_err("Expected list of (doc_id, json_bytes) tuples")
            })?;
            if tuple.len() != 2 {
                return Err(PyValueError::new_err(
                    "Each item must be a (doc_id, json_bytes) tuple",
                ));
            }
            let doc_id: String = tuple.get_item(0)?.extract()?;
            let json_bytes: Vec<u8> = tuple.get_item(1)?.extract()?;

            // Write raw bytes directly - no parsing!
            store
                .put_raw_line(&doc_id, &json_bytes)
                .map_err(|e| PyIOError::new_err(format!("Write failed: {}", e)))?;
            count += 1;
        }

        Ok(count)
    }

    /// Write complete JSONL blob (fastest bulk write - single FFI call, single buffer copy).
    /// jsonl_blob: Pre-serialized JSONL bytes (newline-separated JSON objects with "_id" field).
    /// doc_ids: List of document IDs in order matching the lines.
    fn write_jsonl(&self, jsonl_blob: &[u8], doc_ids: Vec<String>) -> PyResult<usize> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;

        store
            .write_jsonl_blob(jsonl_blob, &doc_ids)
            .map_err(|e| PyIOError::new_err(format!("Write failed: {}", e)))
    }

    /// Delete a document.
    fn delete(&self, doc_id: &str) -> PyResult<()> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        store
            .delete(doc_id)
            .map_err(|e| PyKeyError::new_err(format!("Delete failed: {}", e)))?;
        Ok(())
    }

    /// Flush pending writes and refresh mmap for reads.
    fn flush(&self) -> PyResult<()> {
        let mut store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        store
            .flush()
            .map_err(|e| PyIOError::new_err(format!("Flush failed: {}", e)))?;
        // Refresh mmap after writes for consistent reads
        store
            .refresh_mmap()
            .map_err(|e| PyIOError::new_err(format!("Mmap refresh failed: {}", e)))?;
        Ok(())
    }

    /// Get document count.
    fn count(&self) -> PyResult<usize> {
        let store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        Ok(store.len())
    }

    /// Check if document exists.
    fn exists(&self, doc_id: &str) -> PyResult<bool> {
        let store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        Ok(store.exists(doc_id))
    }

    /// Scan all documents (mmap + parallel SIMD parsing).
    fn scan(&self, py: Python<'_>) -> PyResult<PyObject> {
        let store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        let docs = store
            .scan()
            .map_err(|e| PyIOError::new_err(format!("Scan failed: {}", e)))?;

        let list = PyList::empty_bound(py);
        for doc in docs {
            list.append(json_to_py(py, &doc)?)?;
        }
        Ok(list.into())
    }

    /// Scan and return raw JSON bytes (fastest - zero parsing, use with orjson).
    fn scan_raw(&self, py: Python<'_>) -> PyResult<PyObject> {
        let store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        let raw_docs = store
            .scan_raw()
            .map_err(|e| PyIOError::new_err(format!("Scan failed: {}", e)))?;

        // Convert to list of Python bytes objects
        let list = PyList::empty_bound(py);
        for doc in raw_docs {
            let bytes = pyo3::types::PyBytes::new_bound(py, &doc);
            list.append(bytes)?;
        }
        Ok(list.into())
    }

    /// List all document IDs.
    fn list_doc_ids(&self) -> PyResult<Vec<String>> {
        let store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;
        Ok(store.doc_ids())
    }

    /// Read entire JSONL file as bytes (fastest bulk read).
    /// Returns raw JSONL content - caller splits and parses.
    fn read_jsonl_blob(&self, py: Python<'_>) -> PyResult<PyObject> {
        let store = self
            .store
            .lock()
            .map_err(|e| PyValueError::new_err(format!("Lock error: {}", e)))?;

        if let Some(data) = store.get_raw_data() {
            Ok(pyo3::types::PyBytes::new_bound(py, data).into())
        } else {
            Ok(pyo3::types::PyBytes::new_bound(py, b"").into())
        }
    }

    fn __len__(&self) -> PyResult<usize> {
        self.count()
    }

    fn __contains__(&self, doc_id: &str) -> PyResult<bool> {
        self.exists(doc_id)
    }

    fn __repr__(&self) -> String {
        let count = self.store.lock().map(|s| s.len()).unwrap_or(0);
        format!(
            "NativeStore(root={:?}, collection={:?}, count={})",
            self.root, self.collection, count
        )
    }
}

/// Iterator for scanning documents.
#[pyclass]
pub struct ScanIterator {
    scanner: std::vec::IntoIter<serde_json::Value>,
}

#[pymethods]
impl ScanIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> Option<PyObject> {
        self.scanner.next().and_then(|v| json_to_py(py, &v).ok())
    }
}

/// Get the ZDS version.
#[pyfunction]
fn version() -> &'static str {
    zippy_data::ZDS_VERSION
}

/// Python module definition.
#[pymodule]
fn _zippy_data(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NativeStore>()?;
    m.add_class::<ScanIterator>()?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}
