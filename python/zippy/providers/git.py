"""
Git provider for loading ZDS datasets from any Git repository.

Supports loading datasets from any Git host:
- GitHub: "username/repo" or "github.com/username/repo"
- GitLab: "gitlab.com/username/repo"
- Bitbucket: "bitbucket.org/username/repo"
- Self-hosted: "git.example.com/username/repo"

Examples:
    # Load from GitHub (default host)
    dataset = load_remote("zippydata/example-datasets")
    
    # Load from GitLab
    dataset = load_remote("gitlab.com/user/repo")
    
    # Load specific revision
    dataset = load_remote("zippydata/example-datasets", revision="v1.0")
    
    # Load subdirectory
    dataset = load_remote("zippydata/example-datasets", path="sentiment")
    
    # Load with authentication (for private repos)
    dataset = load_remote("myorg/private-data", token="ghp_...")
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .base import Provider, DatasetInfo


# Known Git hosts with their base URLs
GIT_HOSTS = {
    "github": "github.com",
    "github.com": "github.com",
    "gitlab": "gitlab.com",
    "gitlab.com": "gitlab.com",
    "bitbucket": "bitbucket.org",
    "bitbucket.org": "bitbucket.org",
    "codeberg": "codeberg.org",
    "codeberg.org": "codeberg.org",
    
}


class GitProvider(Provider):
    """
    Provider for loading datasets from any Git repository.
    
    This provider uses git clone for downloading, which:
    - Works with GitHub, GitLab, Bitbucket, and self-hosted Git servers
    - Supports public and private repos (with token)
    - Supports all git features (branches, tags, commits)
    - Handles large files via git-lfs
    - Caches efficiently with git's object storage
    """
    
    name = "git"
    default_host = "github.com"
    
    # Regex for parsing Git URIs
    # Matches: "owner/repo", "owner/repo@rev", "host.com/owner/repo@rev"
    REPO_PATTERN = re.compile(
        r"^(?:(?P<host>[a-zA-Z0-9.-]+)/)?(?P<owner>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_.-]+)"
        r"(?:@(?P<revision>[a-zA-Z0-9_./\-]+))?$"
    )
    
    def parse_uri(self, uri: str) -> Dict[str, Any]:
        """
        Parse a Git URI into components.
        
        Formats:
        - "owner/repo" (uses default host: github.com)
        - "owner/repo@branch"
        - "github.com/owner/repo"
        - "gitlab.com/owner/repo@tag"
        - "git.example.com/owner/repo@commit"
        
        Returns:
            Dict with host, owner, repo, revision keys
        """
        match = self.REPO_PATTERN.match(uri)
        if not match:
            raise ValueError(
                f"Invalid Git URI: '{uri}'. "
                f"Expected format: 'owner/repo', 'owner/repo@revision', or 'host/owner/repo'"
            )
        
        host = match.group("host")
        # If host looks like a known host or contains a dot, use it
        # Otherwise, it's part of owner/repo (no host specified)
        if host and ("." in host or host in GIT_HOSTS):
            resolved_host = GIT_HOSTS.get(host, host)
        else:
            # No host specified, treat first part as owner
            resolved_host = self.default_host
            # Re-parse without host
            simple_match = re.match(
                r"^(?P<owner>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_.-]+)"
                r"(?:@(?P<revision>[a-zA-Z0-9_./\-]+))?$",
                uri
            )
            if simple_match:
                return {
                    "host": resolved_host,
                    "owner": simple_match.group("owner"),
                    "repo": simple_match.group("repo"),
                    "revision": simple_match.group("revision"),
                }
        
        return {
            "host": resolved_host,
            "owner": match.group("owner"),
            "repo": match.group("repo"),
            "revision": match.group("revision"),
        }
    
    def get_info(self, uri: str, token: Optional[str] = None, **kwargs) -> DatasetInfo:
        """
        Get information about a Git repository.
        
        Note: For GitHub repos, this makes API calls. For rate limiting,
        provide a token via the `token` parameter or GIT_TOKEN/GITHUB_TOKEN env var.
        """
        parsed = self.parse_uri(uri)
        host = parsed["host"]
        owner = parsed["owner"]
        repo = parsed["repo"]
        revision = parsed["revision"] or "main"
        
        description = None
        
        # Try to get info via API for known hosts
        if host == "github.com":
            description = self._get_github_info(owner, repo, token)
        elif host == "gitlab.com":
            description = self._get_gitlab_info(owner, repo, token)
        
        return DatasetInfo(
            name=f"{owner}/{repo}",
            provider=self.name,
            uri=f"git://{host}/{owner}/{repo}",
            revision=revision,
            description=description,
        )
    
    def _get_github_info(self, owner: str, repo: str, token: Optional[str]) -> Optional[str]:
        """Get description from GitHub API."""
        try:
            import urllib.request
            import json
            
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            headers = {"Accept": "application/vnd.github.v3+json"}
            token = token or os.environ.get("GIT_TOKEN") or os.environ.get("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"token {token}"
            
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data.get("description")
        except Exception:
            return None
    
    def _get_gitlab_info(self, owner: str, repo: str, token: Optional[str]) -> Optional[str]:
        """Get description from GitLab API."""
        try:
            import urllib.request
            import json
            
            project_path = f"{owner}%2F{repo}"
            api_url = f"https://gitlab.com/api/v4/projects/{project_path}"
            headers = {}
            token = token or os.environ.get("GIT_TOKEN") or os.environ.get("GITLAB_TOKEN")
            if token:
                headers["PRIVATE-TOKEN"] = token
            
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data.get("description")
        except Exception:
            return None
    
    def download(
        self,
        uri: str,
        cache_dir: Optional[Path] = None,
        revision: Optional[str] = None,
        path: Optional[str] = None,
        force: bool = False,
        token: Optional[str] = None,
        depth: int = 1,
        **kwargs
    ) -> Path:
        """
        Download a dataset from a Git repository.
        
        Args:
            uri: Git URI (owner/repo, host/owner/repo, or owner/repo@revision)
            cache_dir: Local cache directory
            revision: Override revision from URI
            path: Subdirectory within the repo to use
            force: Force re-download even if cached
            token: Git authentication token (for private repos)
            depth: Git clone depth (1 for shallow, 0 for full)
            
        Returns:
            Path to the downloaded dataset directory
        """
        parsed = self.parse_uri(uri)
        host = parsed["host"]
        owner = parsed["owner"]
        repo = parsed["repo"]
        revision = revision or parsed["revision"] or "main"
        
        # Get cache directory
        cache_dir = self.get_cache_dir(cache_dir)
        
        # Create cache path: ~/.cache/zds/git/host/owner/repo/revision
        repo_cache = cache_dir / "git" / host / owner / repo / revision
        
        # Check if already cached
        if repo_cache.exists() and not force:
            # Update if needed (git pull)
            self._update_repo(repo_cache, revision)
        else:
            # Clone the repository
            self._clone_repo(host, owner, repo, revision, repo_cache, token, depth)
        
        # If path specified, return subdirectory
        if path:
            dataset_path = repo_cache / path
            if not dataset_path.exists():
                raise FileNotFoundError(
                    f"Path '{path}' not found in repository {host}/{owner}/{repo}"
                )
            return dataset_path
        
        return repo_cache
    
    def _clone_repo(
        self,
        host: str,
        owner: str,
        repo: str,
        revision: str,
        target_dir: Path,
        token: Optional[str] = None,
        depth: int = 1,
    ) -> None:
        """Clone a Git repository from any host."""
        # Get token from environment if not provided
        token = token or os.environ.get("GIT_TOKEN")
        if not token and host == "github.com":
            token = os.environ.get("GITHUB_TOKEN")
        elif not token and host == "gitlab.com":
            token = os.environ.get("GITLAB_TOKEN")
        
        # Build clone URL
        if token:
            clone_url = f"https://{token}@{host}/{owner}/{repo}.git"
        else:
            clone_url = f"https://{host}/{owner}/{repo}.git"
        
        # Ensure parent directory exists
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing directory if present
        if target_dir.exists():
            shutil.rmtree(target_dir)
        
        # Build git clone command
        cmd = ["git", "clone"]
        if depth > 0:
            cmd.extend(["--depth", str(depth)])
        cmd.extend(["--branch", revision, clone_url, str(target_dir)])
        
        try:
            # First try with branch
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            # If branch doesn't exist, clone default and checkout
            cmd = ["git", "clone"]
            if depth > 0:
                cmd.extend(["--depth", str(depth)])
            cmd.extend([clone_url, str(target_dir)])
            
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Checkout specific revision
            subprocess.run(
                ["git", "checkout", revision],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
            )
    
    def _update_repo(self, repo_dir: Path, revision: str) -> None:
        """Update an existing repository."""
        try:
            # Fetch latest
            subprocess.run(
                ["git", "fetch", "--depth=1", "origin", revision],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            # Reset to latest
            subprocess.run(
                ["git", "reset", "--hard", f"origin/{revision}"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Update failed, but we have a cached version - continue
            pass
    
    @staticmethod
    def is_available() -> bool:
        """Check if git is available on the system."""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
