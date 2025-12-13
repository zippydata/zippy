"""
Base provider interface and registry for remote storage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Type, Any
import tempfile
import os


@dataclass
class DatasetInfo:
    """Information about a remote dataset."""
    name: str
    provider: str
    uri: str
    revision: Optional[str] = None
    path: Optional[str] = None
    size_bytes: Optional[int] = None
    last_modified: Optional[str] = None
    description: Optional[str] = None
    
    def __repr__(self) -> str:
        return f"DatasetInfo(name='{self.name}', provider='{self.provider}', uri='{self.uri}')"


class Provider(ABC):
    """
    Abstract base class for remote storage providers.
    
    Providers are responsible for:
    1. Parsing URIs in their format
    2. Downloading datasets to local cache
    3. Providing metadata about remote datasets
    
    Example implementation:
        class MyProvider(Provider):
            name = "my_provider"
            
            def download(self, uri, cache_dir, **kwargs):
                # Download and return local path
                ...
    """
    
    name: str = "base"
    
    @abstractmethod
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        revision: Optional[str] = None,
        path: Optional[str] = None,
        force: bool = False,
        **kwargs
    ) -> Path:
        """
        Download a dataset from remote storage.
        
        Args:
            uri: Remote URI (format depends on provider)
            cache_dir: Local directory for caching (uses default if None)
            revision: Version/branch/tag to download (provider-specific)
            path: Subpath within the repository/bucket
            force: Force re-download even if cached
            **kwargs: Provider-specific options
            
        Returns:
            Path to the downloaded dataset directory
        """
        pass
    
    @abstractmethod
    def get_info(self, uri: str, **kwargs) -> DatasetInfo:
        """
        Get information about a remote dataset without downloading.
        
        Args:
            uri: Remote URI
            **kwargs: Provider-specific options
            
        Returns:
            DatasetInfo with metadata about the dataset
        """
        pass
    
    @abstractmethod
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """
        Parse a URI into its components.
        
        Args:
            uri: Remote URI string
            
        Returns:
            Dictionary with parsed components (provider-specific)
        """
        pass
    
    def get_cache_dir(self, cache_dir: Optional[Path] = None) -> Path:
        """Get the cache directory, creating if needed."""
        if cache_dir is None:
            cache_dir = Path(
                os.environ.get("ZDS_CACHE_DIR", 
                Path.home() / ".cache" / "zds")
            )
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir


class ProviderRegistry:
    """
    Registry of available storage providers.
    
    Providers are registered by scheme (e.g., "github", "s3", "gcs").
    The registry provides URI parsing and automatic provider selection.
    """
    
    _providers: Dict[str, Type[Provider]] = {}
    _default_provider: str = "github"
    
    @classmethod
    def register(cls, scheme: str, provider_class: Type[Provider]) -> None:
        """Register a provider for a URI scheme."""
        cls._providers[scheme.lower()] = provider_class
    
    @classmethod
    def get(cls, scheme: str) -> Type[Provider]:
        """Get a provider class by scheme."""
        scheme = scheme.lower()
        if scheme not in cls._providers:
            available = ", ".join(sorted(cls._providers.keys()))
            raise ValueError(
                f"Unknown provider scheme: '{scheme}'. "
                f"Available: {available}"
            )
        return cls._providers[scheme]
    
    @classmethod
    def get_instance(cls, scheme: str) -> Provider:
        """Get a provider instance by scheme."""
        return cls.get(scheme)()
    
    @classmethod
    def parse_uri(cls, uri: str) -> tuple[str, str]:
        """
        Parse a URI to determine the provider and normalized URI.
        
        Supports formats:
        - "scheme://path" -> (scheme, path)
        - "user/repo" -> (default_provider, "user/repo")
        - "user/repo@revision" -> (default_provider, "user/repo@revision")
        
        Returns:
            Tuple of (scheme, normalized_uri)
        """
        # Check for explicit scheme
        if "://" in uri:
            scheme, rest = uri.split("://", 1)
            return scheme.lower(), rest
        
        # No scheme - use default provider (GitHub-style user/repo)
        return cls._default_provider, uri
    
    @classmethod
    def list_providers(cls) -> Dict[str, Type[Provider]]:
        """List all registered providers."""
        return dict(cls._providers)
    
    @classmethod
    def set_default(cls, scheme: str) -> None:
        """Set the default provider for URIs without scheme."""
        if scheme.lower() not in cls._providers:
            raise ValueError(f"Unknown provider: {scheme}")
        cls._default_provider = scheme.lower()
