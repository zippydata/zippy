"""
Stub providers for remote storage services.

These providers are placeholders for future implementation.
They raise NotImplementedError when used, but are registered
in the provider registry to enable URI parsing and validation.

To contribute an implementation, see the GitHubProvider as a reference.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from .base import Provider, DatasetInfo


class S3Provider(Provider):
    """
    Amazon S3 provider (stub).
    
    Planned URI format:
        s3://bucket/path/to/dataset
        
    Planned features:
        - AWS credentials from environment/config
        - IAM role support
        - Presigned URL support
        - Multipart download for large files
        
    To implement, consider using boto3:
        pip install boto3
    """
    
    name = "s3"
    
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """Parse S3 URI: bucket/path/to/dataset"""
        parts = uri.split("/", 1)
        return {
            "bucket": parts[0],
            "key": parts[1] if len(parts) > 1 else "",
        }
    
    def get_info(self, uri: str, **kwargs) -> DatasetInfo:
        raise NotImplementedError(
            "S3 provider is not yet implemented. "
            "Contributions welcome! See zippy/providers/github.py for reference."
        )
    
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        **kwargs
    ) -> Path:
        raise NotImplementedError(
            "S3 provider is not yet implemented. "
            "To use S3, download the dataset manually and use load_dataset with a local path.\n\n"
            "Example with AWS CLI:\n"
            "  aws s3 sync s3://bucket/dataset ./local_dataset\n"
            "  dataset = load_dataset('./local_dataset')"
        )


class GCSProvider(Provider):
    """
    Google Cloud Storage provider (stub).
    
    Planned URI format:
        gs://bucket/path/to/dataset
        gcs://bucket/path/to/dataset
        
    Planned features:
        - Google Application Default Credentials
        - Service account key support
        - Signed URL support
        
    To implement, consider using google-cloud-storage:
        pip install google-cloud-storage
    """
    
    name = "gcs"
    
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """Parse GCS URI: bucket/path/to/dataset"""
        parts = uri.split("/", 1)
        return {
            "bucket": parts[0],
            "blob": parts[1] if len(parts) > 1 else "",
        }
    
    def get_info(self, uri: str, **kwargs) -> DatasetInfo:
        raise NotImplementedError(
            "GCS provider is not yet implemented. "
            "Contributions welcome! See zippy/providers/github.py for reference."
        )
    
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        **kwargs
    ) -> Path:
        raise NotImplementedError(
            "GCS provider is not yet implemented. "
            "To use GCS, download the dataset manually and use load_dataset with a local path.\n\n"
            "Example with gsutil:\n"
            "  gsutil -m cp -r gs://bucket/dataset ./local_dataset\n"
            "  dataset = load_dataset('./local_dataset')"
        )


class AzureProvider(Provider):
    """
    Azure Blob Storage provider (stub).
    
    Planned URI format:
        azure://container/path/to/dataset
        az://container/path/to/dataset
        
    Planned features:
        - Azure AD authentication
        - Connection string support
        - SAS token support
        
    To implement, consider using azure-storage-blob:
        pip install azure-storage-blob
    """
    
    name = "azure"
    
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """Parse Azure URI: container/path/to/dataset"""
        parts = uri.split("/", 1)
        return {
            "container": parts[0],
            "blob": parts[1] if len(parts) > 1 else "",
        }
    
    def get_info(self, uri: str, **kwargs) -> DatasetInfo:
        raise NotImplementedError(
            "Azure provider is not yet implemented. "
            "Contributions welcome! See zippy/providers/github.py for reference."
        )
    
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        **kwargs
    ) -> Path:
        raise NotImplementedError(
            "Azure provider is not yet implemented. "
            "To use Azure, download the dataset manually and use load_dataset with a local path.\n\n"
            "Example with azcopy:\n"
            "  azcopy copy 'https://account.blob.core.windows.net/container/dataset' './local_dataset' --recursive\n"
            "  dataset = load_dataset('./local_dataset')"
        )


class FTPProvider(Provider):
    """
    FTP/SFTP provider (stub).
    
    Planned URI format:
        ftp://host/path/to/dataset
        sftp://host/path/to/dataset
        
    Planned features:
        - Anonymous and authenticated access
        - SFTP with key-based auth
        - Passive mode support
        
    To implement, consider using paramiko (SFTP) or ftplib (FTP):
        pip install paramiko
    """
    
    name = "ftp"
    
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """Parse FTP URI: host/path/to/dataset"""
        parts = uri.split("/", 1)
        return {
            "host": parts[0],
            "path": "/" + parts[1] if len(parts) > 1 else "/",
        }
    
    def get_info(self, uri: str, **kwargs) -> DatasetInfo:
        raise NotImplementedError(
            "FTP provider is not yet implemented. "
            "Contributions welcome! See zippy/providers/github.py for reference."
        )
    
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        **kwargs
    ) -> Path:
        raise NotImplementedError(
            "FTP provider is not yet implemented. "
            "To use FTP, download the dataset manually and use load_dataset with a local path.\n\n"
            "Example with wget:\n"
            "  wget -r ftp://host/path/dataset -P ./local_dataset\n"
            "  dataset = load_dataset('./local_dataset')"
        )


class HTTPProvider(Provider):
    """
    HTTP/HTTPS provider (stub).
    
    Planned URI format:
        https://example.com/path/to/dataset.zds
        
    Planned features:
        - Direct .zds file download
        - Directory listing (when available)
        - Resume interrupted downloads
        - Authentication (Basic, Bearer)
        
    This provider is for direct HTTP downloads, not for services
    with their own providers (GitHub, HuggingFace, etc.).
    """
    
    name = "http"
    
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """Parse HTTP URI"""
        return {"url": uri}
    
    def get_info(self, uri: str, **kwargs) -> DatasetInfo:
        raise NotImplementedError(
            "HTTP provider is not yet implemented. "
            "Contributions welcome! See zippy/providers/github.py for reference."
        )
    
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        **kwargs
    ) -> Path:
        raise NotImplementedError(
            "HTTP provider is not yet implemented. "
            "To use HTTP, download the dataset manually and use load_dataset with a local path.\n\n"
            "Example with wget:\n"
            "  wget https://example.com/dataset.zds\n"
            "  unzip dataset.zds -d ./local_dataset\n"
            "  dataset = load_dataset('./local_dataset')"
        )


class HuggingFaceProvider(Provider):
    """
    HuggingFace Hub provider (stub).
    
    Planned URI format:
        hf://username/dataset
        huggingface://username/dataset
        
    Planned features:
        - Download ZDS datasets from HuggingFace Hub
        - Authentication with HF tokens
        - Dataset versioning
        
    Note: This is for loading ZDS-format datasets uploaded to HuggingFace,
    not for converting HuggingFace Arrow datasets to ZDS.
    
    To implement, consider using huggingface_hub:
        pip install huggingface_hub
    """
    
    name = "huggingface"
    
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """Parse HuggingFace URI: username/dataset"""
        parts = uri.split("/", 1)
        return {
            "owner": parts[0],
            "dataset": parts[1] if len(parts) > 1 else "",
        }
    
    def get_info(self, uri: str, **kwargs) -> DatasetInfo:
        raise NotImplementedError(
            "HuggingFace provider is not yet implemented. "
            "Contributions welcome! See zippy/providers/github.py for reference."
        )
    
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        **kwargs
    ) -> Path:
        raise NotImplementedError(
            "HuggingFace provider is not yet implemented. "
            "For now, use the huggingface_hub library directly:\n\n"
            "  from huggingface_hub import snapshot_download\n"
            "  path = snapshot_download('username/dataset')\n"
            "  dataset = load_dataset(path)"
        )
