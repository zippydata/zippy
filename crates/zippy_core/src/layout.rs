//! ZDS directory layout and path utilities.

use std::path::{Path, PathBuf};

use crate::Result;

/// ZDS directory layout constants and path helpers.
pub struct Layout;

impl Layout {
    // Top-level directories
    pub const COLLECTIONS_DIR: &'static str = "collections";
    pub const METADATA_DIR: &'static str = "metadata";

    // Collection subdirectories
    pub const DOCS_DIR: &'static str = "docs";
    pub const META_DIR: &'static str = "meta";

    // Metadata files
    pub const SCHEMA_REGISTRY_FILE: &'static str = "schemas.jsonl";
    pub const DOC_INDEX_FILE: &'static str = "doc_index.jsonl";
    pub const ORDER_FILE: &'static str = "order.ids";
    pub const JOURNAL_FILE: &'static str = "journal.log";
    pub const MANIFEST_FILE: &'static str = "manifest.json";
    pub const ROOT_MANIFEST_FILE: &'static str = "root_manifest.json";

    pub const VERSION: &'static str = "0.1.0";

    // Path builders for root-level directories
    pub fn collections_dir(root: &Path) -> PathBuf {
        root.join(Self::COLLECTIONS_DIR)
    }

    pub fn metadata_dir(root: &Path) -> PathBuf {
        root.join(Self::METADATA_DIR)
    }

    pub fn root_manifest(root: &Path) -> PathBuf {
        Self::metadata_dir(root).join(Self::ROOT_MANIFEST_FILE)
    }

    // Path builders for collection-level directories
    pub fn collection_dir(root: &Path, collection: &str) -> PathBuf {
        Self::collections_dir(root).join(collection)
    }

    pub fn docs_dir(root: &Path, collection: &str) -> PathBuf {
        Self::collection_dir(root, collection).join(Self::DOCS_DIR)
    }

    pub fn meta_dir(root: &Path, collection: &str) -> PathBuf {
        Self::collection_dir(root, collection).join(Self::META_DIR)
    }

    // Path builders for specific files
    pub fn doc_file(root: &Path, collection: &str, doc_id: &str) -> PathBuf {
        Self::docs_dir(root, collection).join(format!("{}.json", doc_id))
    }

    pub fn schema_registry(root: &Path, collection: &str) -> PathBuf {
        Self::meta_dir(root, collection).join(Self::SCHEMA_REGISTRY_FILE)
    }

    pub fn doc_index(root: &Path, collection: &str) -> PathBuf {
        Self::meta_dir(root, collection).join(Self::DOC_INDEX_FILE)
    }

    pub fn order_file(root: &Path, collection: &str) -> PathBuf {
        Self::meta_dir(root, collection).join(Self::ORDER_FILE)
    }

    pub fn journal_file(root: &Path, collection: &str) -> PathBuf {
        Self::meta_dir(root, collection).join(Self::JOURNAL_FILE)
    }

    pub fn manifest_file(root: &Path, collection: &str) -> PathBuf {
        Self::meta_dir(root, collection).join(Self::MANIFEST_FILE)
    }

    /// Validate that a path is a valid ZDS root.
    pub fn validate(root: &Path) -> Result<()> {
        if !root.exists() {
            return Err(crate::Error::InvalidContainer(format!(
                "Path does not exist: {}",
                root.display()
            )));
        }

        let collections = Self::collections_dir(root);
        if !collections.exists() {
            return Err(crate::Error::InvalidContainer(format!(
                "Missing collections directory: {}",
                collections.display()
            )));
        }

        Ok(())
    }

    /// Validate a collection exists and has required structure.
    pub fn validate_collection(root: &Path, collection: &str) -> Result<()> {
        let collection_dir = Self::collection_dir(root, collection);
        if !collection_dir.exists() {
            return Err(crate::Error::CollectionNotFound(collection.to_string()));
        }

        let docs_dir = Self::docs_dir(root, collection);
        if !docs_dir.exists() {
            return Err(crate::Error::InvalidContainer(format!(
                "Missing docs directory: {}",
                docs_dir.display()
            )));
        }

        let meta_dir = Self::meta_dir(root, collection);
        if !meta_dir.exists() {
            return Err(crate::Error::InvalidContainer(format!(
                "Missing meta directory: {}",
                meta_dir.display()
            )));
        }

        Ok(())
    }

    /// Initialize a new ZDS root directory.
    pub fn init_root(root: &Path) -> Result<()> {
        std::fs::create_dir_all(Self::collections_dir(root))?;
        std::fs::create_dir_all(Self::metadata_dir(root))?;
        Ok(())
    }

    /// Initialize a new collection within a ZDS root.
    pub fn init_collection(root: &Path, collection: &str) -> Result<()> {
        std::fs::create_dir_all(Self::docs_dir(root, collection))?;
        std::fs::create_dir_all(Self::meta_dir(root, collection))?;
        Ok(())
    }

    /// Check if a document ID is valid.
    pub fn validate_doc_id(doc_id: &str) -> Result<()> {
        if doc_id.is_empty() {
            return Err(crate::Error::InvalidDocId("empty document ID".to_string()));
        }

        // Only allow alphanumeric, underscore, hyphen, dot
        if !doc_id
            .chars()
            .all(|c| c.is_alphanumeric() || c == '_' || c == '-' || c == '.')
        {
            return Err(crate::Error::InvalidDocId(format!(
                "invalid characters in document ID: {}",
                doc_id
            )));
        }

        // Prevent path traversal
        if doc_id.contains("..") || doc_id.starts_with('.') {
            return Err(crate::Error::InvalidDocId(format!(
                "potentially unsafe document ID: {}",
                doc_id
            )));
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use tempfile::TempDir;

    use super::*;

    #[test]
    fn test_path_builders() {
        let root = Path::new("/data/my_dataset");
        assert_eq!(
            Layout::collections_dir(root),
            PathBuf::from("/data/my_dataset/collections")
        );
        assert_eq!(
            Layout::doc_file(root, "train", "doc001"),
            PathBuf::from("/data/my_dataset/collections/train/docs/doc001.json")
        );
    }

    #[test]
    fn test_init_and_validate() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();

        // Before init, validation fails
        assert!(Layout::validate(root).is_err());

        // After init, validation passes
        Layout::init_root(root).unwrap();
        Layout::validate(root).unwrap();

        // Init collection
        Layout::init_collection(root, "train").unwrap();
        Layout::validate_collection(root, "train").unwrap();
    }

    #[test]
    fn test_doc_id_validation() {
        assert!(Layout::validate_doc_id("doc001").is_ok());
        assert!(Layout::validate_doc_id("my-doc_123.v2").is_ok());
        assert!(Layout::validate_doc_id("").is_err());
        assert!(Layout::validate_doc_id("../evil").is_err());
        assert!(Layout::validate_doc_id(".hidden").is_err());
    }
}
