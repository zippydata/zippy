"""
Remote storage providers for ZDS datasets.

Providers enable loading datasets from remote sources like Git repositories, S3, 
Google Cloud Storage, and more. This follows the HuggingFace pattern of
`load_remote("user/repo")` but with no vendor lock-in.

Supported providers:
- git: Load from any Git repository (GitHub, GitLab, Bitbucket, self-hosted)
- s3: Load from Amazon S3 (stub)
- gcs: Load from Google Cloud Storage (stub)  
- azure: Load from Azure Blob Storage (stub)
- ftp: Load from FTP/SFTP servers (stub)
- http: Load from HTTP URLs (stub)
- huggingface: Load from HuggingFace Hub (stub)

Usage:
    from zippy import load_remote
    
    # Load from GitHub (default, uses git provider)
    dataset = load_remote("username/repo")
    dataset = load_remote("username/repo", path="data/train")
    dataset = load_remote("username/repo", revision="v1.0")
    
    # Load from GitLab or other Git hosts
    dataset = load_remote("git://gitlab.com/user/repo")
    dataset = load_remote("git://bitbucket.org/user/repo")
    
    # Load from specific provider
    dataset = load_remote("s3://bucket/path/to/dataset")
    dataset = load_remote("gs://bucket/path/to/dataset")
    
    # Load from URL
    dataset = load_remote("https://example.com/dataset.zds")
"""

from .base import Provider, ProviderRegistry
from .git import GitProvider
from .stubs import (
    S3Provider,
    GCSProvider, 
    AzureProvider,
    FTPProvider,
    HTTPProvider,
    HuggingFaceProvider,
)

# Register all providers
# Git provider (default) - works with GitHub, GitLab, Bitbucket, any Git host
ProviderRegistry.register("git", GitProvider)
ProviderRegistry.register("github", GitProvider)  # GitHub shorthand
ProviderRegistry.register("gh", GitProvider)  # GitHub alias
ProviderRegistry.register("gitlab", GitProvider)  # GitLab shorthand
ProviderRegistry.register("gl", GitProvider)  # GitLab alias
ProviderRegistry.register("bitbucket", GitProvider)  # Bitbucket shorthand
ProviderRegistry.register("bb", GitProvider)  # Bitbucket alias

# Cloud storage providers
ProviderRegistry.register("s3", S3Provider)
ProviderRegistry.register("gcs", GCSProvider)
ProviderRegistry.register("gs", GCSProvider)  # Alias
ProviderRegistry.register("azure", AzureProvider)
ProviderRegistry.register("az", AzureProvider)  # Alias

# Other providers
ProviderRegistry.register("ftp", FTPProvider)
ProviderRegistry.register("sftp", FTPProvider)
ProviderRegistry.register("http", HTTPProvider)
ProviderRegistry.register("https", HTTPProvider)
ProviderRegistry.register("hf", HuggingFaceProvider)
ProviderRegistry.register("huggingface", HuggingFaceProvider)

__all__ = [
    "Provider",
    "ProviderRegistry",
    "GitProvider",
    "S3Provider",
    "GCSProvider",
    "AzureProvider",
    "FTPProvider",
    "HTTPProvider",
    "HuggingFaceProvider",
]
