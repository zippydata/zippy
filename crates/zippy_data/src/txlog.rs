//! Transaction log for crash-safe writes.

use std::{
    io::{BufRead, BufReader, Write},
    path::Path,
};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::{Error, Layout, Result};

/// Journal entry types.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "op")]
pub enum JournalEntry {
    #[serde(rename = "PUT")]
    Put {
        timestamp: DateTime<Utc>,
        doc_id: String,
        schema_id: String,
        size: u64,
    },
    #[serde(rename = "DELETE")]
    Delete {
        timestamp: DateTime<Utc>,
        doc_id: String,
    },
    #[serde(rename = "COMMIT")]
    Commit {
        timestamp: DateTime<Utc>,
        batch_id: u64,
    },
    #[serde(rename = "CHECKPOINT")]
    Checkpoint { timestamp: DateTime<Utc> },
}

impl JournalEntry {
    /// Create a PUT entry.
    pub fn put(doc_id: impl Into<String>, schema_id: impl Into<String>, size: u64) -> Self {
        JournalEntry::Put {
            timestamp: Utc::now(),
            doc_id: doc_id.into(),
            schema_id: schema_id.into(),
            size,
        }
    }

    /// Create a DELETE entry.
    pub fn delete(doc_id: impl Into<String>) -> Self {
        JournalEntry::Delete {
            timestamp: Utc::now(),
            doc_id: doc_id.into(),
        }
    }

    /// Create a COMMIT entry.
    pub fn commit(batch_id: u64) -> Self {
        JournalEntry::Commit {
            timestamp: Utc::now(),
            batch_id,
        }
    }

    /// Create a CHECKPOINT entry.
    pub fn checkpoint() -> Self {
        JournalEntry::Checkpoint {
            timestamp: Utc::now(),
        }
    }

    /// Get the timestamp of this entry.
    pub fn timestamp(&self) -> &DateTime<Utc> {
        match self {
            JournalEntry::Put { timestamp, .. } => timestamp,
            JournalEntry::Delete { timestamp, .. } => timestamp,
            JournalEntry::Commit { timestamp, .. } => timestamp,
            JournalEntry::Checkpoint { timestamp } => timestamp,
        }
    }
}

/// Transaction log for crash recovery.
pub struct TransactionLog {
    path: std::path::PathBuf,
    file: std::fs::File,
    next_batch_id: u64,
}

impl TransactionLog {
    /// Open or create a transaction log.
    pub fn open(root: &Path, collection: &str) -> Result<Self> {
        let path = Layout::journal_file(root, collection);

        // Ensure directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let file = std::fs::OpenOptions::new()
            .create(true)
            .read(true)
            .append(true)
            .open(&path)?;

        // Find the highest batch_id for continuing
        let next_batch_id = Self::find_next_batch_id(&path)?;

        Ok(TransactionLog {
            path,
            file,
            next_batch_id,
        })
    }

    fn find_next_batch_id(path: &Path) -> Result<u64> {
        if !path.exists() {
            return Ok(1);
        }

        let file = std::fs::File::open(path)?;
        let reader = BufReader::new(file);
        let mut max_batch_id: u64 = 0;

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            if let Ok(JournalEntry::Commit { batch_id, .. }) =
                serde_json::from_str::<JournalEntry>(&line)
            {
                max_batch_id = max_batch_id.max(batch_id);
            }
        }

        Ok(max_batch_id + 1)
    }

    /// Append an entry to the journal.
    pub fn append(&mut self, entry: &JournalEntry) -> Result<()> {
        let line = serde_json::to_string(entry)?;
        writeln!(self.file, "{}", line)?;
        self.file.sync_data()?;
        Ok(())
    }

    /// Commit the current batch.
    pub fn commit(&mut self) -> Result<u64> {
        let batch_id = self.next_batch_id;
        self.append(&JournalEntry::commit(batch_id))?;
        self.next_batch_id += 1;
        Ok(batch_id)
    }

    /// Write a checkpoint.
    pub fn checkpoint(&mut self) -> Result<()> {
        self.append(&JournalEntry::checkpoint())?;
        Ok(())
    }

    /// Get uncommitted entries since last commit/checkpoint.
    pub fn get_uncommitted(&self) -> Result<Vec<JournalEntry>> {
        let file = std::fs::File::open(&self.path)?;
        let reader = BufReader::new(file);

        let mut uncommitted: Vec<JournalEntry> = Vec::new();

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }

            let entry: JournalEntry = serde_json::from_str(&line)
                .map_err(|e| Error::JournalCorrupted(format!("Invalid entry: {} ({})", line, e)))?;

            match entry {
                JournalEntry::Commit { .. } | JournalEntry::Checkpoint { .. } => {
                    uncommitted.clear();
                }
                _ => {
                    uncommitted.push(entry);
                }
            }
        }

        Ok(uncommitted)
    }

    /// Replay uncommitted entries (for crash recovery).
    pub fn replay<F>(&self, mut handler: F) -> Result<()>
    where
        F: FnMut(&JournalEntry) -> Result<()>,
    {
        for entry in self.get_uncommitted()? {
            handler(&entry)?;
        }
        Ok(())
    }

    /// Truncate the journal (after successful checkpoint).
    pub fn truncate(&mut self) -> Result<()> {
        // Close current file
        drop(std::mem::replace(
            &mut self.file,
            std::fs::File::open("/dev/null")?,
        ));

        // Truncate and reopen
        self.file = std::fs::OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&self.path)?;

        // Write a fresh checkpoint
        self.checkpoint()?;
        Ok(())
    }

    /// Get the next batch ID.
    pub fn next_batch_id(&self) -> u64 {
        self.next_batch_id
    }
}

#[cfg(test)]
mod tests {
    use tempfile::TempDir;

    use super::*;

    #[test]
    fn test_journal_operations() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();
        Layout::init_root(root).unwrap();
        Layout::init_collection(root, "test").unwrap();

        let mut log = TransactionLog::open(root, "test").unwrap();

        // Write some entries
        log.append(&JournalEntry::put("doc1", "schema1", 100))
            .unwrap();
        log.append(&JournalEntry::put("doc2", "schema1", 200))
            .unwrap();

        // Before commit, entries are uncommitted
        let uncommitted = log.get_uncommitted().unwrap();
        assert_eq!(uncommitted.len(), 2);

        // After commit, they're committed
        log.commit().unwrap();
        let uncommitted = log.get_uncommitted().unwrap();
        assert_eq!(uncommitted.len(), 0);
    }

    #[test]
    fn test_crash_recovery() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();
        Layout::init_root(root).unwrap();
        Layout::init_collection(root, "test").unwrap();

        // Simulate crash: write entries but don't commit
        {
            let mut log = TransactionLog::open(root, "test").unwrap();
            log.append(&JournalEntry::put("doc1", "schema1", 100))
                .unwrap();
            log.append(&JournalEntry::put("doc2", "schema1", 200))
                .unwrap();
            // No commit - simulating crash
        }

        // Reopen and check uncommitted entries
        let log = TransactionLog::open(root, "test").unwrap();
        let uncommitted = log.get_uncommitted().unwrap();
        assert_eq!(uncommitted.len(), 2);
    }
}
