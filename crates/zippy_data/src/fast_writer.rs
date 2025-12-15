//! Fast JSONL-based writer for high-throughput ingestion.
//!
//! Optimizations:
//! - FxHashMap for faster string hashing
//! - memchr for SIMD newline search
//! - Binary index format for fast load/save
//! - Sorted offset iteration for cache-friendly reads
//! - mmap + parallel SIMD JSON parsing

use std::{
    collections::HashMap,
    fs::{File, OpenOptions},
    io::{BufRead, BufReader, BufWriter, Read, Seek, SeekFrom, Write},
    path::{Path, PathBuf},
    sync::{Arc, Weak},
};

use memchr::memchr_iter;
use memmap2::Mmap;
use once_cell::sync::Lazy;
use parking_lot::RwLock;
use rayon::prelude::*;
use rustc_hash::FxHashMap;
use serde_json::Value;

use crate::{lock::WriteLock, Error, Layout, Result};

/// Open mode for ZDS stores.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum OpenMode {
    /// Read-only mode - no writes allowed, no lock acquired.
    Read,
    /// Read-write mode - writes allowed, exclusive lock acquired.
    ReadWrite,
}

impl Default for OpenMode {
    fn default() -> Self {
        OpenMode::ReadWrite
    }
}

/// Global cache of open ZDSRoot instances by (canonical_path, mode).
/// Uses weak references so roots are cleaned up when all handles are dropped.
static ROOT_CACHE: Lazy<RwLock<HashMap<(PathBuf, OpenMode), Weak<ZDSRootInner>>>> =
    Lazy::new(|| RwLock::new(HashMap::new()));

/// Entry in the in-memory index (16 bytes, aligned).
#[derive(Debug, Clone, Copy)]
#[repr(C)]
pub struct IndexEntry {
    pub offset: u64,
    pub length: u32,
    _padding: u32, // Explicit padding for alignment
}

/// Binary index header (magic + version + count).
const INDEX_MAGIC: u32 = 0x5A445349; // "ZDSI"
const INDEX_VERSION: u32 = 1;

/// High-performance JSONL-based store.
pub struct FastStore {
    #[allow(dead_code)]
    root: PathBuf,
    #[allow(dead_code)]
    collection: String,
    data_file: PathBuf,
    index_file: PathBuf,
    index: FxHashMap<String, IndexEntry>, // FxHashMap for faster string hashing
    writer: Option<BufWriter<File>>,
    current_offset: u64,
    pending_count: usize,
    batch_size: usize,
    /// Memory-mapped view for fast reads (lazily initialized)
    mmap: Option<Arc<Mmap>>,
    /// Open mode (read-only or read-write)
    mode: OpenMode,
}

impl FastStore {
    /// Open or create a fast store in read-write mode.
    pub fn open(
        root: impl AsRef<Path>,
        collection: impl AsRef<str>,
        batch_size: usize,
    ) -> Result<Self> {
        Self::open_with_mode(root, collection, batch_size, OpenMode::ReadWrite)
    }

    /// Open a fast store with explicit mode.
    pub fn open_with_mode(
        root: impl AsRef<Path>,
        collection: impl AsRef<str>,
        batch_size: usize,
        mode: OpenMode,
    ) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let collection = collection.as_ref().to_string();

        // Create directory structure (only in ReadWrite mode)
        let meta_dir = Layout::meta_dir(&root, &collection);
        if mode == OpenMode::ReadWrite {
            std::fs::create_dir_all(&meta_dir)?;
        }

        let data_file = meta_dir.join("data.jsonl");
        let index_file = meta_dir.join("index.bin");

        // Load index (try binary first, fall back to text, then rebuild)
        let mut index = FxHashMap::default();
        let current_offset = if data_file.exists() {
            if index_file.exists() {
                // Try binary format first
                if Self::load_index_binary(&index_file, &mut index).is_err() {
                    // Fall back to text format
                    index.clear();
                    let _ = Self::load_index_text(&index_file, &mut index);
                }
            }
            if index.is_empty() {
                // Rebuild index from data file
                Self::rebuild_index(&data_file, &mut index)?;
            }
            std::fs::metadata(&data_file)?.len()
        } else {
            0
        };

        // Open writer in append mode with larger buffer (only in ReadWrite mode)
        let writer = if mode == OpenMode::ReadWrite {
            let file = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&data_file)?;
            Some(BufWriter::with_capacity(256 * 1024, file)) // 256KB buffer
        } else {
            None
        };

        // Create mmap if data file exists and has content
        let mmap = if data_file.exists() && current_offset > 0 {
            let file = File::open(&data_file)?;
            let mmap = unsafe { Mmap::map(&file)? };
            Some(Arc::new(mmap))
        } else {
            None
        };

        Ok(FastStore {
            root,
            collection,
            data_file,
            index_file,
            index,
            writer,
            current_offset,
            pending_count: 0,
            batch_size,
            mmap,
            mode,
        })
    }

    /// Get the open mode.
    pub fn mode(&self) -> OpenMode {
        self.mode
    }

    /// Check if this store is writable.
    pub fn is_writable(&self) -> bool {
        self.mode == OpenMode::ReadWrite
    }

    /// Refresh mmap after writes (call after flush for read consistency)
    pub fn refresh_mmap(&mut self) -> Result<()> {
        if self.data_file.exists() && self.current_offset > 0 {
            let file = File::open(&self.data_file)?;
            let mmap = unsafe { Mmap::map(&file)? };
            self.mmap = Some(Arc::new(mmap));
        }
        Ok(())
    }

    /// Load binary index format (fast path).
    /// Format: [magic:u32][version:u32][count:u64] + [id_len:u16, id_bytes, entry:12bytes]...
    fn load_index_binary(path: &Path, index: &mut FxHashMap<String, IndexEntry>) -> Result<()> {
        let mut file = File::open(path)?;

        // Read header
        let mut header = [0u8; 16];
        file.read_exact(&mut header)?;

        let magic = u32::from_le_bytes([header[0], header[1], header[2], header[3]]);
        let version = u32::from_le_bytes([header[4], header[5], header[6], header[7]]);
        let count = u64::from_le_bytes([
            header[8], header[9], header[10], header[11], header[12], header[13], header[14],
            header[15],
        ]);

        if magic != INDEX_MAGIC || version != INDEX_VERSION {
            return Err(Error::Io(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "Invalid index format",
            )));
        }

        index.reserve(count as usize);

        // Read entries
        for _ in 0..count {
            // Read doc_id length
            let mut len_buf = [0u8; 2];
            file.read_exact(&mut len_buf)?;
            let id_len = u16::from_le_bytes(len_buf) as usize;

            // Read doc_id
            let mut id_buf = vec![0u8; id_len];
            file.read_exact(&mut id_buf)?;
            let doc_id = String::from_utf8_lossy(&id_buf).into_owned();

            // Read entry (12 bytes)
            let mut entry_buf = [0u8; 12];
            file.read_exact(&mut entry_buf)?;
            let offset = u64::from_le_bytes([
                entry_buf[0],
                entry_buf[1],
                entry_buf[2],
                entry_buf[3],
                entry_buf[4],
                entry_buf[5],
                entry_buf[6],
                entry_buf[7],
            ]);
            let length =
                u32::from_le_bytes([entry_buf[8], entry_buf[9], entry_buf[10], entry_buf[11]]);

            index.insert(
                doc_id,
                IndexEntry {
                    offset,
                    length,
                    _padding: 0,
                },
            );
        }

        Ok(())
    }

    /// Load text-based index format (legacy fallback).
    fn load_index_text(path: &Path, index: &mut FxHashMap<String, IndexEntry>) -> Result<()> {
        let file = File::open(path)?;
        let reader = BufReader::new(file);

        for line in reader.lines() {
            let line = line?;
            let parts: Vec<&str> = line.split('\t').collect();
            if parts.len() == 3 {
                let doc_id = parts[0].to_string();
                let offset: u64 = parts[1].parse().unwrap_or(0);
                let length: u32 = parts[2].parse().unwrap_or(0);
                index.insert(
                    doc_id,
                    IndexEntry {
                        offset,
                        length,
                        _padding: 0,
                    },
                );
            }
        }
        Ok(())
    }

    /// Rebuild index from data file using SIMD newline search.
    fn rebuild_index(path: &Path, index: &mut FxHashMap<String, IndexEntry>) -> Result<()> {
        let file = File::open(path)?;
        let mmap = unsafe { Mmap::map(&file)? };
        let data = &mmap[..];

        let mut offset: u64 = 0;
        let mut line_start = 0;

        // Use memchr for SIMD newline search
        for newline_pos in memchr_iter(b'\n', data) {
            let line = &data[line_start..newline_pos];
            let length = (newline_pos - line_start + 1) as u32;

            // Fast _id extraction without full JSON parse
            if let Some(doc_id) = Self::extract_id_fast(line) {
                index.insert(
                    doc_id,
                    IndexEntry {
                        offset,
                        length,
                        _padding: 0,
                    },
                );
            }

            offset += length as u64;
            line_start = newline_pos + 1;
        }

        // Handle last line without trailing newline
        if line_start < data.len() {
            let line = &data[line_start..];
            let length = (data.len() - line_start) as u32;
            if let Some(doc_id) = Self::extract_id_fast(line) {
                index.insert(
                    doc_id,
                    IndexEntry {
                        offset,
                        length,
                        _padding: 0,
                    },
                );
            }
        }

        Ok(())
    }

    /// Fast _id extraction using pattern matching (avoids full JSON parse).
    fn extract_id_fast(line: &[u8]) -> Option<String> {
        // Look for "_id":" pattern
        const PATTERN: &[u8] = b"\"_id\":\"";

        if let Some(start) = line.windows(PATTERN.len()).position(|w| w == PATTERN) {
            let id_start = start + PATTERN.len();
            // Find closing quote
            if let Some(end_offset) = memchr::memchr(b'"', &line[id_start..]) {
                let id_bytes = &line[id_start..id_start + end_offset];
                return Some(String::from_utf8_lossy(id_bytes).into_owned());
            }
        }
        None
    }

    /// Save index in binary format (fast).
    fn save_index(&self) -> Result<()> {
        let file = File::create(&self.index_file)?;
        let mut writer = BufWriter::with_capacity(256 * 1024, file);

        // Write header
        writer.write_all(&INDEX_MAGIC.to_le_bytes())?;
        writer.write_all(&INDEX_VERSION.to_le_bytes())?;
        writer.write_all(&(self.index.len() as u64).to_le_bytes())?;

        // Write entries
        for (doc_id, entry) in &self.index {
            let id_bytes = doc_id.as_bytes();
            writer.write_all(&(id_bytes.len() as u16).to_le_bytes())?;
            writer.write_all(id_bytes)?;
            writer.write_all(&entry.offset.to_le_bytes())?;
            writer.write_all(&entry.length.to_le_bytes())?;
        }

        writer.flush()?;
        Ok(())
    }

    /// Put a document.
    pub fn put(&mut self, doc_id: impl Into<String>, doc: Value) -> Result<()> {
        if self.mode == OpenMode::Read {
            return Err(Error::ReadOnly("cannot put in read-only mode".to_string()));
        }
        let doc_id = doc_id.into();
        Layout::validate_doc_id(&doc_id)?;

        // Create document with _id field
        let mut doc_with_id = serde_json::Map::new();
        doc_with_id.insert("_id".to_string(), Value::String(doc_id.clone()));

        if let Value::Object(obj) = doc {
            for (k, v) in obj {
                doc_with_id.insert(k, v);
            }
        }

        // Serialize to compact JSON
        let line = serde_json::to_string(&Value::Object(doc_with_id))?;
        self.put_raw_line(doc_id, line.as_bytes())
    }

    /// Put a document as raw JSON bytes (fastest path).
    /// The line should be valid JSON with "_id" field already included.
    pub fn put_raw_line(&mut self, doc_id: impl Into<String>, line_bytes: &[u8]) -> Result<()> {
        if self.mode == OpenMode::Read {
            return Err(Error::ReadOnly("cannot put in read-only mode".to_string()));
        }
        let doc_id = doc_id.into();
        let length = line_bytes.len() as u32 + 1; // +1 for newline

        // Write to buffer
        if let Some(writer) = &mut self.writer {
            writer.write_all(line_bytes)?;
            writer.write_all(b"\n")?;
        }

        // Update index
        self.index.insert(
            doc_id,
            IndexEntry {
                offset: self.current_offset,
                length,
                _padding: 0,
            },
        );
        self.current_offset += length as u64;
        self.pending_count += 1;

        // Auto-flush if batch size reached
        if self.pending_count >= self.batch_size {
            self.flush()?;
        }

        Ok(())
    }

    /// Write a complete JSONL blob with doc_ids (fastest bulk path).
    /// Uses SIMD newline search and single write for maximum throughput.
    pub fn write_jsonl_blob(&mut self, jsonl_data: &[u8], doc_ids: &[String]) -> Result<usize> {
        if self.mode == OpenMode::Read {
            return Err(Error::ReadOnly(
                "cannot write in read-only mode".to_string(),
            ));
        }
        let writer = self.writer.as_mut().ok_or_else(|| {
            Error::Io(std::io::Error::new(
                std::io::ErrorKind::NotConnected,
                "Writer not available",
            ))
        })?;

        // Write entire blob at once (single syscall)
        writer.write_all(jsonl_data)?;

        // Ensure trailing newline
        if !jsonl_data.is_empty() && jsonl_data.last() != Some(&b'\n') {
            writer.write_all(b"\n")?;
        }

        // Build index using SIMD newline search
        let mut count = 0;
        let mut line_start = 0;
        let mut doc_idx = 0;

        for newline_pos in memchr_iter(b'\n', jsonl_data) {
            if doc_idx < doc_ids.len() && line_start < newline_pos {
                let length = (newline_pos - line_start + 1) as u32;

                // Use reference to avoid clone when possible
                self.index.insert(
                    doc_ids[doc_idx].clone(),
                    IndexEntry {
                        offset: self.current_offset,
                        length,
                        _padding: 0,
                    },
                );
                self.current_offset += length as u64;
                count += 1;
                doc_idx += 1;
            }
            line_start = newline_pos + 1;
        }

        // Handle last line without trailing newline
        if line_start < jsonl_data.len() && doc_idx < doc_ids.len() {
            let length = (jsonl_data.len() - line_start + 1) as u32; // +1 for added newline

            self.index.insert(
                doc_ids[doc_idx].clone(),
                IndexEntry {
                    offset: self.current_offset,
                    length,
                    _padding: 0,
                },
            );
            self.current_offset += length as u64;
            count += 1;
        }

        self.pending_count += count;
        Ok(count)
    }

    /// Get a document by ID (uses mmap if available).
    pub fn get(&self, doc_id: &str) -> Result<Value> {
        let entry = self
            .index
            .get(doc_id)
            .ok_or_else(|| Error::DocumentNotFound(doc_id.to_string()))?;

        // Use mmap for zero-copy access if available
        if let Some(mmap) = &self.mmap {
            let start = entry.offset as usize;
            let end = start + entry.length as usize;

            if end <= mmap.len() {
                let mut buffer = mmap[start..end].to_vec();
                if buffer.last() == Some(&b'\n') {
                    buffer.pop();
                }

                // Use simd-json for faster parsing
                let mut doc: Value = simd_json::from_slice(&mut buffer).map_err(|e| {
                    Error::Json(serde_json::Error::io(std::io::Error::new(
                        std::io::ErrorKind::InvalidData,
                        e.to_string(),
                    )))
                })?;

                if let Value::Object(ref mut obj) = doc {
                    obj.remove("_id");
                }

                return Ok(doc);
            }
        }

        // Fallback to regular file I/O
        let mut file = File::open(&self.data_file)?;
        file.seek(SeekFrom::Start(entry.offset))?;

        let mut buffer = vec![0u8; entry.length as usize];
        std::io::Read::read_exact(&mut file, &mut buffer)?;

        if buffer.last() == Some(&b'\n') {
            buffer.pop();
        }

        let mut doc: Value = serde_json::from_slice(&buffer)?;

        if let Value::Object(ref mut obj) = doc {
            obj.remove("_id");
        }

        Ok(doc)
    }

    /// Delete a document.
    pub fn delete(&mut self, doc_id: &str) -> Result<()> {
        if !self.index.contains_key(doc_id) {
            return Err(Error::DocumentNotFound(doc_id.to_string()));
        }
        self.index.remove(doc_id);
        Ok(())
    }

    /// Check if document exists.
    pub fn exists(&self, doc_id: &str) -> bool {
        self.index.contains_key(doc_id)
    }

    /// Get document count.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    /// Check if empty.
    pub fn is_empty(&self) -> bool {
        self.index.is_empty()
    }

    /// Get all document IDs.
    pub fn doc_ids(&self) -> Vec<String> {
        self.index.keys().cloned().collect()
    }

    /// Flush pending writes to disk.
    pub fn flush(&mut self) -> Result<()> {
        if let Some(writer) = &mut self.writer {
            writer.flush()?;
        }
        self.pending_count = 0;
        self.save_index()?;
        Ok(())
    }

    /// Scan all documents using mmap + parallel SIMD parsing.
    pub fn scan(&self) -> Result<Vec<Value>> {
        if self.index.is_empty() {
            return Ok(Vec::new());
        }

        // Use mmap for zero-copy access
        if let Some(mmap) = &self.mmap {
            return self.scan_mmap_parallel(mmap);
        }

        // Fallback to regular file reading if mmap not available
        self.scan_file()
    }

    /// Scan using memory-mapped file with parallel SIMD parsing.
    fn scan_mmap_parallel(&self, mmap: &Mmap) -> Result<Vec<Value>> {
        let entries: Vec<_> = self.index.values().collect();

        // Direct parallel iteration - simpler and faster
        let docs: Vec<Value> = entries
            .par_iter()
            .filter_map(|entry| {
                let start = entry.offset as usize;
                let end = start + entry.length as usize;

                if end <= mmap.len() {
                    let mut slice = mmap[start..end].to_vec();
                    if slice.last() == Some(&b'\n') {
                        slice.pop();
                    }

                    if let Ok(mut doc) = simd_json::from_slice::<Value>(&mut slice) {
                        if let Value::Object(ref mut obj) = doc {
                            obj.remove("_id");
                        }
                        return Some(doc);
                    }
                }
                None
            })
            .collect();

        Ok(docs)
    }

    /// Fallback scan using regular file I/O.
    fn scan_file(&self) -> Result<Vec<Value>> {
        if !self.data_file.exists() {
            return Ok(Vec::new());
        }

        let file = File::open(&self.data_file)?;
        let reader = BufReader::new(file);
        let mut docs = Vec::with_capacity(self.index.len());

        for line in reader.lines() {
            let line = line?;
            if let Ok(mut doc) = serde_json::from_str::<Value>(&line) {
                if let Value::Object(ref mut obj) = doc {
                    let doc_id = obj.remove("_id");
                    if let Some(Value::String(id)) = doc_id {
                        if self.index.contains_key(&id) {
                            docs.push(doc);
                        }
                    }
                }
            }
        }

        Ok(docs)
    }

    /// Scan and return raw JSON bytes (fastest - zero parsing).
    pub fn scan_raw(&self) -> Result<Vec<Vec<u8>>> {
        if self.index.is_empty() {
            return Ok(Vec::new());
        }

        if let Some(mmap) = &self.mmap {
            let entries: Vec<_> = self.index.values().collect();

            let raw: Vec<Vec<u8>> = entries
                .par_iter()
                .filter_map(|entry| {
                    let start = entry.offset as usize;
                    let end = start + entry.length as usize;

                    if end <= mmap.len() {
                        let mut slice = mmap[start..end].to_vec();
                        if slice.last() == Some(&b'\n') {
                            slice.pop();
                        }
                        return Some(slice);
                    }
                    None
                })
                .collect();

            return Ok(raw);
        }

        // Fallback: create mmap on demand
        if self.data_file.exists() {
            let file = File::open(&self.data_file)?;
            let mmap = unsafe { Mmap::map(&file)? };
            let entries: Vec<_> = self.index.values().collect();

            let raw: Vec<Vec<u8>> = entries
                .par_iter()
                .filter_map(|entry| {
                    let start = entry.offset as usize;
                    let end = start + entry.length as usize;

                    if end <= mmap.len() {
                        let mut slice = mmap[start..end].to_vec();
                        if slice.last() == Some(&b'\n') {
                            slice.pop();
                        }
                        return Some(slice);
                    }
                    None
                })
                .collect();

            return Ok(raw);
        }

        Ok(Vec::new())
    }

    /// Get the raw JSONL data as bytes (zero-copy from mmap).
    /// This is the fastest way to get all data for bulk processing.
    pub fn get_raw_data(&self) -> Option<&[u8]> {
        self.mmap.as_ref().map(|m| &**m as &[u8])
    }

    /// Compact the data file by removing deleted entries.
    pub fn compact(&mut self) -> Result<()> {
        self.flush()?;

        let tmp_file = self.data_file.with_extension("tmp");
        let mut new_index = FxHashMap::default();
        let mut offset: u64 = 0;

        {
            let src = File::open(&self.data_file)?;
            let reader = BufReader::new(src);
            let dst = File::create(&tmp_file)?;
            let mut writer = BufWriter::new(dst);

            for line in reader.lines() {
                let line = line?;
                if let Ok(doc) = serde_json::from_str::<Value>(&line) {
                    if let Some(doc_id) = doc.get("_id").and_then(|v| v.as_str()) {
                        if self.index.contains_key(doc_id) {
                            let length = line.len() as u32 + 1;
                            writeln!(writer, "{}", line)?;
                            new_index.insert(
                                doc_id.to_string(),
                                IndexEntry {
                                    offset,
                                    length,
                                    _padding: 0,
                                },
                            );
                            offset += length as u64;
                        }
                    }
                }
            }
            writer.flush()?;
        }

        // Atomic replace
        std::fs::rename(&tmp_file, &self.data_file)?;
        self.index = new_index;
        self.current_offset = offset;
        self.save_index()?;

        // Reopen writer
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.data_file)?;
        self.writer = Some(BufWriter::with_capacity(64 * 1024, file));

        Ok(())
    }
}

impl Drop for FastStore {
    fn drop(&mut self) {
        let _ = self.flush();
    }
}

/// Inner state for ZDSRoot, shared via Arc.
struct ZDSRootInner {
    root: PathBuf,
    batch_size: usize,
    mode: OpenMode,
    /// Write lock (only held in ReadWrite mode)
    write_lock: Option<WriteLock>,
}

impl std::fmt::Debug for ZDSRootInner {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ZDSRootInner")
            .field("root", &self.root)
            .field("batch_size", &self.batch_size)
            .field("mode", &self.mode)
            .field("write_lock", &self.write_lock.is_some())
            .finish()
    }
}

/// Root handle for a ZDS store directory.
///
/// This struct represents a ZDS root directory without binding to a specific collection.
/// It allows opening multiple collections from the same root safely, avoiding corruption
/// when writing to multiple collections simultaneously.
///
/// Roots are **memoized** by (path, mode): opening the same path twice returns the same
/// shared instance, ensuring a single write lock protects the entire store.
///
/// # Example
///
/// ```ignore
/// use zippy_data::{ZDSRoot, OpenMode};
///
/// // Open in read-write mode (default)
/// let root = ZDSRoot::open("./data", 1000, OpenMode::ReadWrite)?;
/// let train = root.collection("train")?;
/// let test = root.collection("test")?;
///
/// train.put("doc1", json!({"split": "train"}))?;
/// test.put("doc1", json!({"split": "test"}))?;
///
/// // Open read-only (no lock, parallel readers allowed)
/// let reader = ZDSRoot::open("./data", 1000, OpenMode::Read)?;
/// ```
#[derive(Clone)]
pub struct ZDSRoot {
    inner: Arc<ZDSRootInner>,
}

impl std::fmt::Debug for ZDSRoot {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ZDSRoot")
            .field("root", &self.inner.root)
            .field("batch_size", &self.inner.batch_size)
            .field("mode", &self.inner.mode)
            .finish()
    }
}

impl ZDSRoot {
    /// Open or create a ZDS root directory.
    ///
    /// This initializes the root directory structure but does not open any collection.
    /// Use `collection()` to get a handle to a specific collection.
    ///
    /// # Memoization
    ///
    /// Roots are cached by (canonical_path, mode). Opening the same path multiple times
    /// returns the same shared instance, ensuring consistent locking.
    ///
    /// # Locking
    ///
    /// - `OpenMode::ReadWrite`: Acquires an exclusive write lock. Only one writer allowed.
    /// - `OpenMode::Read`: No lock acquired. Multiple readers allowed.
    pub fn open(root: impl AsRef<Path>, batch_size: usize, mode: OpenMode) -> Result<Self> {
        let root_path = root.as_ref();

        // Initialize root directory structure first (needed for canonicalize)
        if mode == OpenMode::ReadWrite {
            Layout::init_root(root_path)?;
        }

        // Canonicalize path for consistent caching (after directory exists)
        let canonical =
            std::fs::canonicalize(root_path).unwrap_or_else(|_| root_path.to_path_buf());
        let cache_key = (canonical.clone(), mode);

        // Check cache first
        {
            let cache = ROOT_CACHE.read();
            if let Some(weak) = cache.get(&cache_key) {
                if let Some(inner) = weak.upgrade() {
                    return Ok(ZDSRoot { inner });
                }
            }
        }

        // Not in cache or expired - create new
        let mut cache = ROOT_CACHE.write();

        // Double-check after acquiring write lock
        if let Some(weak) = cache.get(&cache_key) {
            if let Some(inner) = weak.upgrade() {
                return Ok(ZDSRoot { inner });
            }
        }

        // Acquire write lock if in ReadWrite mode
        let write_lock = if mode == OpenMode::ReadWrite {
            Some(WriteLock::acquire(root_path)?)
        } else {
            None
        };

        let inner = Arc::new(ZDSRootInner {
            root: root_path.to_path_buf(),
            batch_size,
            mode,
            write_lock,
        });

        // Store weak reference in cache
        cache.insert(cache_key, Arc::downgrade(&inner));

        Ok(ZDSRoot { inner })
    }

    /// Open in read-write mode (convenience method).
    pub fn open_rw(root: impl AsRef<Path>, batch_size: usize) -> Result<Self> {
        Self::open(root, batch_size, OpenMode::ReadWrite)
    }

    /// Open in read-only mode (convenience method).
    pub fn open_readonly(root: impl AsRef<Path>, batch_size: usize) -> Result<Self> {
        Self::open(root, batch_size, OpenMode::Read)
    }

    /// Get the root path.
    pub fn root_path(&self) -> &Path {
        &self.inner.root
    }

    /// Get the default batch size.
    pub fn batch_size(&self) -> usize {
        self.inner.batch_size
    }

    /// Get the open mode.
    pub fn mode(&self) -> OpenMode {
        self.inner.mode
    }

    /// Check if this root is writable.
    pub fn is_writable(&self) -> bool {
        self.inner.mode == OpenMode::ReadWrite
    }

    /// Open a collection within this ZDS root.
    ///
    /// Creates the collection if it doesn't exist (in ReadWrite mode).
    /// Returns an error if attempting to create in Read mode.
    pub fn collection(&self, name: impl AsRef<str>) -> Result<FastStore> {
        self.collection_with_batch_size(name, self.inner.batch_size)
    }

    /// Open a collection with a custom batch size.
    pub fn collection_with_batch_size(
        &self,
        name: impl AsRef<str>,
        batch_size: usize,
    ) -> Result<FastStore> {
        let name = name.as_ref();

        // Check if collection exists
        let exists = self.collection_exists(name);

        // In read mode, collection must exist
        if self.inner.mode == OpenMode::Read && !exists {
            return Err(Error::CollectionNotFound(name.to_string()));
        }

        FastStore::open_with_mode(&self.inner.root, name, batch_size, self.inner.mode)
    }

    /// List all collections in this ZDS root.
    pub fn list_collections(&self) -> Result<Vec<String>> {
        let collections_dir = Layout::collections_dir(&self.inner.root);
        if !collections_dir.exists() {
            return Ok(Vec::new());
        }

        let mut collections = Vec::new();
        for entry in std::fs::read_dir(collections_dir)? {
            let entry = entry?;
            if entry.file_type()?.is_dir() {
                if let Some(name) = entry.file_name().to_str() {
                    collections.push(name.to_string());
                }
            }
        }
        collections.sort();
        Ok(collections)
    }

    /// Check if a collection exists.
    pub fn collection_exists(&self, name: &str) -> bool {
        Layout::collection_dir(&self.inner.root, name).exists()
    }

    /// Close the root explicitly, releasing any locks.
    ///
    /// This removes the root from the cache and drops the write lock if held.
    /// After calling this, the root handle is still valid but will need to
    /// reacquire the lock if opened again.
    pub fn close(&self) {
        let canonical =
            std::fs::canonicalize(&self.inner.root).unwrap_or_else(|_| self.inner.root.clone());
        let cache_key = (canonical, self.inner.mode);

        let mut cache = ROOT_CACHE.write();
        cache.remove(&cache_key);
        // The write lock will be released when the last Arc reference is dropped
    }

    /// Clear all cached roots (useful for testing).
    #[doc(hidden)]
    pub fn clear_cache() {
        let mut cache = ROOT_CACHE.write();
        cache.clear();
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;
    use tempfile::TempDir;

    use super::*;

    #[test]
    fn test_fast_store_basic() {
        let tmp = TempDir::new().unwrap();
        let mut store = FastStore::open(tmp.path(), "test", 100).unwrap();

        store.put("doc1", json!({"name": "alice"})).unwrap();
        store.flush().unwrap();

        let doc = store.get("doc1").unwrap();
        assert_eq!(doc["name"], "alice");
        assert_eq!(store.len(), 1);
    }

    #[test]
    fn test_zds_root_basic() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();
        let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();

        // Initially no collections
        assert!(root.list_collections().unwrap().is_empty());
        assert!(!root.collection_exists("train"));

        // Create collection via collection()
        let mut train = root.collection("train").unwrap();
        train.put("doc1", json!({"split": "train"})).unwrap();
        train.flush().unwrap();

        // Collection should now exist
        assert!(root.collection_exists("train"));
        assert_eq!(root.list_collections().unwrap(), vec!["train"]);
    }

    #[test]
    fn test_zds_root_multiple_collections() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();
        let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();

        // Create multiple collections from the same root
        let mut train = root.collection("train").unwrap();
        let mut test = root.collection("test").unwrap();
        let mut valid = root.collection("validation").unwrap();

        train
            .put("doc1", json!({"split": "train", "data": 1}))
            .unwrap();
        test.put("doc1", json!({"split": "test", "data": 2}))
            .unwrap();
        valid
            .put("doc1", json!({"split": "validation", "data": 3}))
            .unwrap();

        train.flush().unwrap();
        test.flush().unwrap();
        valid.flush().unwrap();

        // Verify each collection has its own data
        assert_eq!(train.len(), 1);
        assert_eq!(test.len(), 1);
        assert_eq!(valid.len(), 1);

        let train_doc = train.get("doc1").unwrap();
        let test_doc = test.get("doc1").unwrap();
        let valid_doc = valid.get("doc1").unwrap();

        assert_eq!(train_doc["split"], "train");
        assert_eq!(test_doc["split"], "test");
        assert_eq!(valid_doc["split"], "validation");

        // List collections should show all three
        let collections = root.list_collections().unwrap();
        assert_eq!(collections.len(), 3);
        assert!(collections.contains(&"train".to_string()));
        assert!(collections.contains(&"test".to_string()));
        assert!(collections.contains(&"validation".to_string()));
    }

    #[test]
    fn test_zds_root_collection_isolation() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();
        let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();

        // Write same doc ID to different collections
        let mut train = root.collection("train").unwrap();
        let mut test = root.collection("test").unwrap();

        train.put("doc_001", json!({"value": 100})).unwrap();
        test.put("doc_001", json!({"value": 200})).unwrap();

        train.flush().unwrap();
        test.flush().unwrap();

        // Each collection should have independent data
        assert_eq!(train.get("doc_001").unwrap()["value"], 100);
        assert_eq!(test.get("doc_001").unwrap()["value"], 200);
    }

    #[test]
    fn test_zds_root_custom_batch_size() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();
        let root = ZDSRoot::open_rw(tmp.path(), 1000).unwrap();

        assert_eq!(root.batch_size(), 1000);

        // Open collection with custom batch size
        let mut store = root.collection_with_batch_size("custom", 500).unwrap();
        store.put("doc1", json!({"test": true})).unwrap();
        store.flush().unwrap();

        assert!(root.collection_exists("custom"));
    }

    #[test]
    fn test_zds_root_reopen() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();

        // Create root and write data
        {
            let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();
            let mut train = root.collection("train").unwrap();
            train.put("doc1", json!({"persisted": true})).unwrap();
            train.flush().unwrap();
        }

        // Reopen and verify data persists
        ZDSRoot::clear_cache();
        {
            let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();
            assert!(root.collection_exists("train"));

            let train = root.collection("train").unwrap();
            let doc = train.get("doc1").unwrap();
            assert_eq!(doc["persisted"], true);
        }
    }

    #[test]
    fn test_zds_root_read_only() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();

        // Create some data first
        {
            let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();
            let mut train = root.collection("train").unwrap();
            train.put("doc1", json!({"value": 42})).unwrap();
            train.flush().unwrap();
        }

        // Clear cache and open read-only
        ZDSRoot::clear_cache();
        {
            let root = ZDSRoot::open_readonly(tmp.path(), 100).unwrap();
            assert!(!root.is_writable());
            assert_eq!(root.mode(), OpenMode::Read);

            // Can read existing collection
            let train = root.collection("train").unwrap();
            assert_eq!(train.get("doc1").unwrap()["value"], 42);

            // Cannot open non-existent collection in read mode
            let result = root.collection("nonexistent");
            assert!(result.is_err());
        }
    }

    #[test]
    fn test_zds_root_read_only_write_fails() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();

        // Create some data first
        {
            let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();
            let mut train = root.collection("train").unwrap();
            train.put("doc1", json!({"value": 42})).unwrap();
            train.flush().unwrap();
        }

        // Clear cache and open read-only
        ZDSRoot::clear_cache();
        {
            let root = ZDSRoot::open_readonly(tmp.path(), 100).unwrap();
            let mut train = root.collection("train").unwrap();

            // Writing should fail
            let result = train.put("doc2", json!({"value": 100}));
            assert!(result.is_err());
            if let Err(Error::ReadOnly(_)) = result {
                // Expected
            } else {
                panic!("Expected ReadOnly error");
            }
        }
    }

    #[test]
    fn test_zds_root_memoization() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();

        // Open same path twice - should return same instance
        let root1 = ZDSRoot::open_rw(tmp.path(), 100).unwrap();
        let root2 = ZDSRoot::open_rw(tmp.path(), 100).unwrap();

        // Both should point to same underlying data (via Arc)
        assert!(Arc::ptr_eq(&root1.inner, &root2.inner));
    }

    #[test]
    fn test_zds_root_close() {
        ZDSRoot::clear_cache();
        let tmp = TempDir::new().unwrap();

        // Open and close - must drop root to release lock
        {
            let root = ZDSRoot::open_rw(tmp.path(), 100).unwrap();
            root.close();
            // root is dropped here, releasing the lock
        }

        // After close + drop, can reopen
        ZDSRoot::clear_cache();
        let root2 = ZDSRoot::open_rw(tmp.path(), 100).unwrap();
        assert!(root2.list_collections().unwrap().is_empty());
    }
}
