//! Container abstraction for folder and archive access.

use std::path::{Path, PathBuf};

use crate::{Error, Layout, Result};

/// Container filesystem abstraction.
#[derive(Debug, Clone)]
pub enum ContainerFS {
    /// Folder-based container (read/write)
    Folder(PathBuf),
    /// ZIP archive container (read-only in v0.1)
    Zip(PathBuf),
}

impl ContainerFS {
    /// Open a container from a path.
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();

        if !path.exists() {
            return Err(Error::InvalidContainer(format!(
                "Path does not exist: {}",
                path.display()
            )));
        }

        if path.is_dir() {
            Ok(ContainerFS::Folder(path.to_path_buf()))
        } else if path.is_file() && path.extension().map(|e| e == "zds").unwrap_or(false) {
            Ok(ContainerFS::Zip(path.to_path_buf()))
        } else {
            Err(Error::InvalidContainer(format!(
                "Expected folder or .zds file, got: {}",
                path.display()
            )))
        }
    }

    /// Create a new folder container.
    pub fn create_folder(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        Layout::init_root(path)?;
        Ok(ContainerFS::Folder(path.to_path_buf()))
    }

    /// Get the root path.
    pub fn root_path(&self) -> &Path {
        match self {
            ContainerFS::Folder(p) => p,
            ContainerFS::Zip(p) => p,
        }
    }

    /// List all collections in the container.
    pub fn list_collections(&self) -> Result<Vec<String>> {
        match self {
            ContainerFS::Folder(root) => {
                let collections_dir = Layout::collections_dir(root);
                if !collections_dir.exists() {
                    return Ok(Vec::new());
                }

                let mut collections = Vec::new();
                for entry in std::fs::read_dir(&collections_dir)? {
                    let entry = entry?;
                    if entry.path().is_dir() {
                        if let Some(name) = entry.file_name().to_str() {
                            collections.push(name.to_string());
                        }
                    }
                }
                collections.sort();
                Ok(collections)
            }
            ContainerFS::Zip(path) => {
                let file = std::fs::File::open(path)?;
                let archive = zip::ZipArchive::new(file)
                    .map_err(|e| Error::Archive(format!("Failed to open archive: {}", e)))?;

                let mut collections = std::collections::HashSet::new();
                for name in archive.file_names() {
                    // Parse paths like "collections/train/docs/..."
                    let parts: Vec<&str> = name.split('/').collect();
                    if parts.len() >= 2 && parts[0] == "collections" {
                        collections.insert(parts[1].to_string());
                    }
                }

                let mut result: Vec<_> = collections.into_iter().collect();
                result.sort();
                Ok(result)
            }
        }
    }

    /// Check if container is folder-based.
    pub fn is_folder(&self) -> bool {
        matches!(self, ContainerFS::Folder(_))
    }

    /// Check if container is archive-based.
    pub fn is_zip(&self) -> bool {
        matches!(self, ContainerFS::Zip(_))
    }

    /// Check if container is writable.
    pub fn is_writable(&self) -> bool {
        self.is_folder()
    }

    /// Read a file from the container.
    pub fn read_file(&self, relative_path: &Path) -> Result<Vec<u8>> {
        match self {
            ContainerFS::Folder(root) => {
                let path = root.join(relative_path);
                Ok(std::fs::read(&path)?)
            }
            ContainerFS::Zip(archive_path) => {
                let file = std::fs::File::open(archive_path)?;
                let mut archive = zip::ZipArchive::new(file)
                    .map_err(|e| Error::Archive(format!("Failed to open archive: {}", e)))?;

                let path_str = relative_path.to_string_lossy();
                let mut entry = archive.by_name(&path_str).map_err(|e| {
                    Error::Archive(format!("File not found in archive: {} ({})", path_str, e))
                })?;

                let mut buffer = Vec::new();
                std::io::Read::read_to_end(&mut entry, &mut buffer)?;
                Ok(buffer)
            }
        }
    }

    /// Read a file as string from the container.
    pub fn read_file_string(&self, relative_path: &Path) -> Result<String> {
        let bytes = self.read_file(relative_path)?;
        String::from_utf8(bytes).map_err(|e| Error::Codec(format!("Invalid UTF-8 in file: {}", e)))
    }

    /// Write a file to the container (folder only).
    pub fn write_file(&self, relative_path: &Path, data: &[u8]) -> Result<()> {
        match self {
            ContainerFS::Folder(root) => {
                let path = root.join(relative_path);
                if let Some(parent) = path.parent() {
                    std::fs::create_dir_all(parent)?;
                }
                std::fs::write(&path, data)?;
                Ok(())
            }
            ContainerFS::Zip(_) => Err(Error::InvalidContainer(
                "Cannot write to archive container".to_string(),
            )),
        }
    }

    /// Check if a file exists in the container.
    pub fn file_exists(&self, relative_path: &Path) -> Result<bool> {
        match self {
            ContainerFS::Folder(root) => {
                let path = root.join(relative_path);
                Ok(path.exists())
            }
            ContainerFS::Zip(archive_path) => {
                let file = std::fs::File::open(archive_path)?;
                let archive = zip::ZipArchive::new(file)
                    .map_err(|e| Error::Archive(format!("Failed to open archive: {}", e)))?;
                let path_str = relative_path.to_string_lossy();
                let exists = archive.file_names().any(|n| n == path_str.as_ref());
                Ok(exists)
            }
        }
    }
}

/// Pack a folder container into a .zds archive.
pub fn pack(source: &Path, dest: &Path) -> Result<()> {
    use std::io::Write;

    use zip::write::FileOptions;

    let file = std::fs::File::create(dest)?;
    let mut archive = zip::ZipWriter::new(file);
    let options = FileOptions::default().compression_method(zip::CompressionMethod::Deflated);

    fn add_dir(
        archive: &mut zip::ZipWriter<std::fs::File>,
        base: &Path,
        current: &Path,
        options: FileOptions,
    ) -> Result<()> {
        for entry in std::fs::read_dir(current)? {
            let entry = entry?;
            let path = entry.path();
            let relative = path.strip_prefix(base).unwrap();
            let name = relative.to_string_lossy();

            if path.is_dir() {
                archive
                    .add_directory(format!("{}/", name), options)
                    .map_err(|e| Error::Archive(format!("Failed to add directory: {}", e)))?;
                add_dir(archive, base, &path, options)?;
            } else {
                archive
                    .start_file(name.to_string(), options)
                    .map_err(|e| Error::Archive(format!("Failed to start file: {}", e)))?;
                let data = std::fs::read(&path)?;
                archive.write_all(&data)?;
            }
        }
        Ok(())
    }

    add_dir(&mut archive, source, source, options)?;
    archive
        .finish()
        .map_err(|e| Error::Archive(format!("Failed to finish archive: {}", e)))?;

    Ok(())
}

/// Unpack a .zds archive into a folder.
pub fn unpack(source: &Path, dest: &Path) -> Result<()> {
    let file = std::fs::File::open(source)?;
    let mut archive = zip::ZipArchive::new(file)
        .map_err(|e| Error::Archive(format!("Failed to open archive: {}", e)))?;

    for i in 0..archive.len() {
        let mut entry = archive
            .by_index(i)
            .map_err(|e| Error::Archive(format!("Failed to read entry: {}", e)))?;

        let outpath = dest.join(entry.name());

        if entry.is_dir() {
            std::fs::create_dir_all(&outpath)?;
        } else {
            if let Some(parent) = outpath.parent() {
                std::fs::create_dir_all(parent)?;
            }
            let mut outfile = std::fs::File::create(&outpath)?;
            std::io::copy(&mut entry, &mut outfile)?;
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use tempfile::TempDir;

    use super::*;

    #[test]
    fn test_folder_container() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path();

        let container = ContainerFS::create_folder(root).unwrap();
        assert!(container.is_folder());
        assert!(container.is_writable());
    }

    #[test]
    fn test_pack_unpack() {
        let tmp = TempDir::new().unwrap();
        let source = tmp.path().join("source");
        let archive = tmp.path().join("test.zds");
        let dest = tmp.path().join("dest");

        // Create source
        ContainerFS::create_folder(&source).unwrap();
        Layout::init_collection(&source, "train").unwrap();
        std::fs::write(
            Layout::doc_file(&source, "train", "doc001"),
            r#"{"test": true}"#,
        )
        .unwrap();

        // Pack
        pack(&source, &archive).unwrap();
        assert!(archive.exists());

        // Unpack
        unpack(&archive, &dest).unwrap();
        assert!(Layout::doc_file(&dest, "train", "doc001").exists());
    }
}
