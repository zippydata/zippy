//! Fast JSONL-based writer for high-throughput ingestion.
//!
//! Optimizations:
//! - FxHashMap for faster string hashing
//! - memchr for SIMD newline search
//! - Binary index format for fast load/save
//! - Sorted offset iteration for cache-friendly reads
//! - mmap + parallel SIMD JSON parsing

use std::{
    fs::{File, OpenOptions},
    io::{BufRead, BufReader, BufWriter, Read, Seek, SeekFrom, Write},
    path::{Path, PathBuf},
    sync::Arc,
};

use memchr::memchr_iter;
use memmap2::Mmap;
use rayon::prelude::*;
use rustc_hash::FxHashMap;
use serde_json::Value;

use crate::{Error, Layout, Result};

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
}

impl FastStore {
    /// Open or create a fast store.
    pub fn open(
        root: impl AsRef<Path>,
        collection: impl AsRef<str>,
        batch_size: usize,
    ) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let collection = collection.as_ref().to_string();

        // Create directory structure
        let meta_dir = Layout::meta_dir(&root, &collection);
        std::fs::create_dir_all(&meta_dir)?;

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

        // Open writer in append mode with larger buffer
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&data_file)?;
        let writer = BufWriter::with_capacity(256 * 1024, file); // 256KB buffer

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
            writer: Some(writer),
            current_offset,
            pending_count: 0,
            batch_size,
            mmap,
        })
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
