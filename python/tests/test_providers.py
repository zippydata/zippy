"""
Tests for remote storage providers.
"""
import pytest
import tempfile
import os
from pathlib import Path

from zippy.providers.base import Provider, ProviderRegistry, DatasetInfo
from zippy.providers.git import GitProvider, GIT_HOSTS
from zippy.providers.stubs import S3Provider, GCSProvider, AzureProvider


class TestProviderRegistry:
    """Tests for the ProviderRegistry class."""
    
    def test_parse_uri_github_shorthand(self):
        """Test parsing GitHub shorthand URIs."""
        scheme, uri = ProviderRegistry.parse_uri("user/repo")
        assert scheme == "github"
        assert uri == "user/repo"
    
    def test_parse_uri_github_with_revision(self):
        """Test parsing GitHub URI with revision."""
        scheme, uri = ProviderRegistry.parse_uri("user/repo@v1.0")
        assert scheme == "github"
        assert uri == "user/repo@v1.0"
    
    def test_parse_uri_s3(self):
        """Test parsing S3 URIs."""
        scheme, uri = ProviderRegistry.parse_uri("s3://bucket/path/to/data")
        assert scheme == "s3"
        assert uri == "bucket/path/to/data"
    
    def test_parse_uri_gcs(self):
        """Test parsing GCS URIs."""
        scheme, uri = ProviderRegistry.parse_uri("gs://bucket/path")
        assert scheme == "gs"
        assert uri == "bucket/path"
    
    def test_parse_uri_https(self):
        """Test parsing HTTPS URIs."""
        scheme, uri = ProviderRegistry.parse_uri("https://example.com/data.zds")
        assert scheme == "https"
        assert uri == "example.com/data.zds"
    
    def test_get_instance(self):
        """Test getting provider instances."""
        provider = ProviderRegistry.get_instance("github")
        assert isinstance(provider, GitProvider)
        
        provider = ProviderRegistry.get_instance("git")
        assert isinstance(provider, GitProvider)
    
    def test_get_instance_unknown(self):
        """Test getting unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            ProviderRegistry.get_instance("unknown_provider")
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = ProviderRegistry.list_providers()
        assert "git" in providers
        assert "github" in providers
        assert "s3" in providers
        assert "gcs" in providers


class TestGitProvider:
    """Tests for the GitProvider class."""
    
    def test_parse_uri_simple(self):
        """Test parsing simple owner/repo format."""
        provider = GitProvider()
        parsed = provider.parse_uri("zippydata/example")
        
        assert parsed["host"] == "github.com"
        assert parsed["owner"] == "zippydata"
        assert parsed["repo"] == "example"
        assert parsed["revision"] is None
    
    def test_parse_uri_with_revision(self):
        """Test parsing owner/repo@revision format."""
        provider = GitProvider()
        parsed = provider.parse_uri("user/repo@v1.0")
        
        assert parsed["host"] == "github.com"
        assert parsed["owner"] == "user"
        assert parsed["repo"] == "repo"
        assert parsed["revision"] == "v1.0"
    
    def test_parse_uri_gitlab(self):
        """Test parsing GitLab URI."""
        provider = GitProvider()
        parsed = provider.parse_uri("gitlab.com/user/repo")
        
        assert parsed["host"] == "gitlab.com"
        assert parsed["owner"] == "user"
        assert parsed["repo"] == "repo"
    
    def test_parse_uri_bitbucket(self):
        """Test parsing Bitbucket URI."""
        provider = GitProvider()
        parsed = provider.parse_uri("bitbucket.org/user/repo@main")
        
        assert parsed["host"] == "bitbucket.org"
        assert parsed["owner"] == "user"
        assert parsed["repo"] == "repo"
        assert parsed["revision"] == "main"
    
    def test_parse_uri_custom_host(self):
        """Test parsing custom Git host URI."""
        provider = GitProvider()
        parsed = provider.parse_uri("git.mycompany.com/team/dataset")
        
        assert parsed["host"] == "git.mycompany.com"
        assert parsed["owner"] == "team"
        assert parsed["repo"] == "dataset"
    
    def test_parse_uri_invalid(self):
        """Test parsing invalid URI raises error."""
        provider = GitProvider()
        with pytest.raises(ValueError, match="Invalid Git URI"):
            provider.parse_uri("invalid")
    
    def test_get_info(self):
        """Test getting dataset info."""
        provider = GitProvider()
        # Use a simple parse - actual API call would require network
        info = provider.get_info("zippydata/test")
        
        assert info.name == "zippydata/test"
        assert info.provider == "git"
        assert "github.com" in info.uri
    
    def test_is_available(self):
        """Test checking if git is available."""
        # Git should be available on most dev machines
        assert GitProvider.is_available() is True
    
    def test_cache_dir(self):
        """Test cache directory resolution."""
        provider = GitProvider()
        
        # Default cache dir
        cache = provider.get_cache_dir(None)
        assert "zds" in str(cache)
        
        # Custom cache dir
        custom = Path("/tmp/my_cache")
        cache = provider.get_cache_dir(custom)
        assert cache == custom


class TestStubProviders:
    """Tests for stub providers."""
    
    def test_s3_provider_not_implemented(self):
        """Test S3 provider raises NotImplementedError."""
        provider = S3Provider()
        with pytest.raises(NotImplementedError, match="S3 provider is not yet implemented"):
            provider.download("bucket/path")
    
    def test_gcs_provider_not_implemented(self):
        """Test GCS provider raises NotImplementedError."""
        provider = GCSProvider()
        with pytest.raises(NotImplementedError, match="GCS provider is not yet implemented"):
            provider.download("bucket/path")
    
    def test_azure_provider_not_implemented(self):
        """Test Azure provider raises NotImplementedError."""
        provider = AzureProvider()
        with pytest.raises(NotImplementedError, match="Azure provider is not yet implemented"):
            provider.download("container/path")
    
    def test_stub_provider_not_implemented_get_info(self):
        """Test stub providers raise NotImplementedError on get_info."""
        provider = S3Provider()
        with pytest.raises(NotImplementedError):
            provider.get_info("bucket/path")


class TestDatasetInfo:
    """Tests for DatasetInfo class."""
    
    def test_datasetinfo_creation(self):
        """Test creating DatasetInfo."""
        info = DatasetInfo(
            name="test/dataset",
            provider="git",
            uri="git://github.com/test/dataset",
            revision="v1.0",
            description="Test dataset",
        )
        
        assert info.name == "test/dataset"
        assert info.provider == "git"
        assert info.revision == "v1.0"
    
    def test_datasetinfo_optional_fields(self):
        """Test DatasetInfo with optional fields."""
        info = DatasetInfo(
            name="test",
            provider="local",
            uri="/path/to/data",
        )
        
        assert info.revision is None
        assert info.description is None


class TestGitHostsMapping:
    """Tests for Git hosts mapping."""
    
    def test_known_hosts(self):
        """Test known hosts mapping."""
        assert GIT_HOSTS["github"] == "github.com"
        assert GIT_HOSTS["gitlab"] == "gitlab.com"
        assert GIT_HOSTS["bitbucket"] == "bitbucket.org"
    
    def test_host_aliases(self):
        """Test host aliases."""
        assert GIT_HOSTS["github.com"] == "github.com"
        assert GIT_HOSTS["gitlab.com"] == "gitlab.com"
