//! Error types for ZDS operations.

use thiserror::Error;

/// Result type alias for ZDS operations.
pub type Result<T> = std::result::Result<T, Error>;

/// Error types for ZDS operations.
#[derive(Error, Debug)]
pub enum Error {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Invalid container: {0}")]
    InvalidContainer(String),

    #[error("Collection not found: {0}")]
    CollectionNotFound(String),

    #[error("Document not found: {0}")]
    DocumentNotFound(String),

    #[error("Schema mismatch: expected {expected}, got {actual}")]
    SchemaMismatch { expected: String, actual: String },

    #[error("Strict mode violation: {0}")]
    StrictModeViolation(String),

    #[error("Journal corrupted: {0}")]
    JournalCorrupted(String),

    #[error("Transaction failed: {0}")]
    TransactionFailed(String),

    #[error("Invalid document ID: {0}")]
    InvalidDocId(String),

    #[error("Archive error: {0}")]
    Archive(String),

    #[error("Validation error: {0}")]
    Validation(String),

    #[error("Codec error: {0}")]
    Codec(String),
}

impl Error {
    /// Check if error is recoverable (can retry operation).
    pub fn is_recoverable(&self) -> bool {
        matches!(self, Error::Io(_) | Error::TransactionFailed(_))
    }

    /// Check if error indicates data corruption.
    pub fn is_corruption(&self) -> bool {
        matches!(self, Error::JournalCorrupted(_) | Error::Validation(_))
    }
}
