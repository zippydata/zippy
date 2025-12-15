//! File locking for ZDS stores.
//!
//! Provides cross-platform write locking using flock (via fs2) plus an
//! explicit lock file for systems where flock is unreliable.

use std::{
    fs::{File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
};

use fs2::FileExt;

use crate::{Error, Result};

/// Lock file name within the ZDS metadata directory.
const LOCK_FILE_NAME: &str = ".zds_write.lock";

/// Metadata written to the lock file for debugging.
#[derive(Debug)]
pub struct LockInfo {
    pub pid: u32,
    pub hostname: String,
    pub timestamp: String,
}

impl LockInfo {
    fn current() -> Self {
        LockInfo {
            pid: std::process::id(),
            hostname: hostname::get()
                .map(|h| h.to_string_lossy().to_string())
                .unwrap_or_else(|_| "unknown".to_string()),
            timestamp: chrono::Utc::now().to_rfc3339(),
        }
    }

    fn serialize(&self) -> String {
        format!(
            "pid={}\nhostname={}\ntimestamp={}\n",
            self.pid, self.hostname, self.timestamp
        )
    }

    fn deserialize(content: &str) -> Option<Self> {
        let mut pid = None;
        let mut hostname = None;
        let mut timestamp = None;

        for line in content.lines() {
            if let Some(val) = line.strip_prefix("pid=") {
                pid = val.parse().ok();
            } else if let Some(val) = line.strip_prefix("hostname=") {
                hostname = Some(val.to_string());
            } else if let Some(val) = line.strip_prefix("timestamp=") {
                timestamp = Some(val.to_string());
            }
        }

        Some(LockInfo {
            pid: pid?,
            hostname: hostname?,
            timestamp: timestamp?,
        })
    }
}

/// A write lock on a ZDS root directory.
///
/// Uses both flock (via fs2) and an explicit lock file for maximum compatibility.
/// The lock is released when this struct is dropped.
pub struct WriteLock {
    /// The lock file handle (keeps flock active)
    #[allow(dead_code)]
    file: File,
    /// Path to the lock file (for cleanup)
    lock_path: PathBuf,
}

impl WriteLock {
    /// Attempt to acquire a write lock on the given ZDS root.
    ///
    /// Returns an error if another process already holds the lock.
    pub fn acquire(root: &Path) -> Result<Self> {
        let metadata_dir = root.join(".zds");
        std::fs::create_dir_all(&metadata_dir)?;

        let lock_path = metadata_dir.join(LOCK_FILE_NAME);

        // Open or create the lock file
        let file = OpenOptions::new()
            .create(true)
            .read(true)
            .write(true)
            .truncate(false)
            .open(&lock_path)?;

        // Try to acquire exclusive flock (non-blocking)
        match file.try_lock_exclusive() {
            Ok(()) => {
                // Got the flock - now write our metadata
                Self::write_lock_info(&lock_path)?;
                Ok(WriteLock { file, lock_path })
            }
            Err(_) => {
                // Failed to get lock - read existing lock info for error message
                let existing = Self::read_lock_info(&lock_path);
                let msg = if let Some(info) = existing {
                    format!(
                        "ZDS store is locked by another process (pid={}, host={}, since={})",
                        info.pid, info.hostname, info.timestamp
                    )
                } else {
                    "ZDS store is locked by another process".to_string()
                };
                Err(Error::WriteLock(msg))
            }
        }
    }

    /// Release the lock explicitly (also happens on drop).
    pub fn release(self) {
        // Drop will handle cleanup
        drop(self);
    }

    fn write_lock_info(path: &Path) -> Result<()> {
        let info = LockInfo::current();
        let mut file = File::create(path)?;
        file.write_all(info.serialize().as_bytes())?;
        file.sync_all()?;
        Ok(())
    }

    fn read_lock_info(path: &Path) -> Option<LockInfo> {
        let mut file = File::open(path).ok()?;
        let mut content = String::new();
        file.read_to_string(&mut content).ok()?;
        LockInfo::deserialize(&content)
    }
}

impl Drop for WriteLock {
    fn drop(&mut self) {
        // Unlock the file (flock is released automatically when file is closed)
        let _ = self.file.unlock();

        // Remove the lock file to clean up explicitly
        let _ = std::fs::remove_file(&self.lock_path);
    }
}

#[cfg(test)]
mod tests {
    use tempfile::TempDir;

    use super::*;

    #[test]
    fn test_acquire_release() {
        let tmp = TempDir::new().unwrap();
        let lock = WriteLock::acquire(tmp.path()).unwrap();

        // Lock file should exist
        let lock_path = tmp.path().join(".zds").join(LOCK_FILE_NAME);
        assert!(lock_path.exists());

        // Release
        lock.release();

        // Lock file should be removed
        assert!(!lock_path.exists());
    }

    #[test]
    fn test_double_lock_fails() {
        let tmp = TempDir::new().unwrap();
        let _lock1 = WriteLock::acquire(tmp.path()).unwrap();

        // Second lock should fail
        let result = WriteLock::acquire(tmp.path());
        assert!(result.is_err());
        if let Err(Error::WriteLock(msg)) = result {
            assert!(msg.contains("locked by another process"));
        } else {
            panic!("Expected WriteLock error");
        }
    }

    #[test]
    fn test_lock_info_serialization() {
        let info = LockInfo {
            pid: 12345,
            hostname: "testhost".to_string(),
            timestamp: "2025-01-01T00:00:00Z".to_string(),
        };

        let serialized = info.serialize();
        let deserialized = LockInfo::deserialize(&serialized).unwrap();

        assert_eq!(deserialized.pid, 12345);
        assert_eq!(deserialized.hostname, "testhost");
        assert_eq!(deserialized.timestamp, "2025-01-01T00:00:00Z");
    }
}
