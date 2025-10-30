"""Backend factory for URI-based backend resolution and instantiation.

This module provides a factory pattern for creating FileBackend instances
from URI strings. It supports multiple URI schemes and allows registration
of custom backend factories.

Supported URI Schemes:
    - file://path - LocalFileBackend for local filesystem
    - git+ssh://url@branch - GitSyncFileBackend over SSH
    - git+https://url@branch - GitSyncFileBackend over HTTPS
    - openai+vector://vs_id - OpenAIVectorStoreFileBackend

Example:
    >>> from f9_file_backend.factory import resolve_backend
    >>> # Create local file backend
    >>> backend = resolve_backend("file:///data/files")
    >>> # Create Git backend with SSH
    >>> backend = resolve_backend("git+ssh://github.com/user/repo@main?ssh_key=/home/user/.ssh/id_rsa")
    >>> # Create OpenAI backend
    >>> backend = resolve_backend("openai+vector://vs_123456?api_key=sk_xxx")

"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from typing import TypeAlias

    from .interfaces import FileBackend, SyncFileBackend

    # Type alias for backend factory functions
    BackendFactoryFunc: TypeAlias = Callable[
        [str, dict[str, Any]],
        FileBackend | SyncFileBackend,
    ]


class BackendFactory:
    """Factory for creating backends from URI strings."""

    def __init__(self) -> None:
        """Initialize the factory with built-in URI scheme handlers."""
        self._factories: dict[str, Callable[[str, dict[str, Any]], Any]] = {
            "file": self._create_file_backend,
            "git+ssh": self._create_git_ssh_backend,
            "git+https": self._create_git_https_backend,
            "openai+vector": self._create_openai_backend,
        }

    def parse_uri(self, uri: str) -> tuple[str, str, dict[str, str]]:
        """Parse a URI into scheme, path, and query parameters.

        Args:
            uri: URI string to parse

        Returns:
            Tuple of (scheme, path, params) where params is a dict of query parameters

        Raises:
            ValueError: If URI format is invalid

        """
        parsed = urlparse(uri)

        if not parsed.scheme:
            msg = f"Invalid URI: missing scheme in '{uri}'"
            raise ValueError(msg)

        # Extract path component - handle both absolute and relative paths
        path = parsed.path or parsed.netloc

        # For file URIs, keep the full path
        if parsed.scheme == "file":
            # file://path or file:///path
            if parsed.netloc:
                path = parsed.netloc + (parsed.path or "")
            else:
                path = parsed.path
        else:
            # For other schemes, reconstruct the path with netloc
            if parsed.netloc:
                if parsed.path:
                    path = f"{parsed.netloc}{parsed.path}"
                else:
                    path = parsed.netloc

        if not path:
            msg = f"Invalid URI: missing path in '{uri}'"
            raise ValueError(msg)

        # Parse query parameters
        params: dict[str, str] = {}
        if parsed.query:
            parsed_params = parse_qs(parsed.query)
            # Convert list values to single strings (take first value)
            params = {
                k: v[0] if isinstance(v, list) else v
                for k, v in parsed_params.items()
            }

        return parsed.scheme, path, params

    def resolve(self, uri: str) -> FileBackend | SyncFileBackend:
        """Create a backend instance from a URI string.

        Args:
            uri: URI string specifying the backend configuration

        Returns:
            FileBackend or SyncFileBackend instance

        Raises:
            ValueError: If URI scheme is unsupported
            FileBackendError: If backend creation fails

        """
        scheme, path, params = self.parse_uri(uri)

        if scheme not in self._factories:
            supported = ", ".join(sorted(self._factories.keys()))
            msg = (
                f"Unsupported URI scheme: '{scheme}'. "
                f"Supported schemes: {supported}"
            )
            raise ValueError(msg)

        factory_func = self._factories[scheme]
        return factory_func(path, params)

    def register(
        self,
        scheme: str,
        factory_func: Callable[[str, dict[str, Any]], Any],
    ) -> None:
        """Register a custom backend factory for a URI scheme.

        Args:
            scheme: URI scheme to register (e.g., "s3", "azure")
            factory_func: Callable that takes (path, params) and returns a FileBackend

        """
        if not callable(factory_func):
            msg = "factory_func must be callable"
            raise TypeError(msg)
        self._factories[scheme] = factory_func

    def _create_file_backend(
        self,
        path: str,
        params: dict[str, Any],
    ) -> FileBackend:
        """Create a LocalFileBackend from URI components.

        Args:
            path: File path
            params: Query parameters (unused for file backend)

        Returns:
            LocalFileBackend instance

        """
        from .local import LocalFileBackend

        create_root = params.get("create_root", "true").lower() == "true"
        return LocalFileBackend(root=path, create_root=create_root)

    def _create_git_ssh_backend(
        self,
        path: str,
        params: dict[str, Any],
    ) -> SyncFileBackend:
        """Create a GitSyncFileBackend from SSH URI.

        URI format: git+ssh://github.com/user/repo@branch?ssh_key=/path&author_name=Bot&author_email=bot@example.com

        Args:
            path: Git remote URL (e.g., github.com/user/repo)
            params: Query parameters (ssh_key, author_name, author_email, branch)

        Returns:
            GitSyncFileBackend instance

        """
        from .git_backend import GitSyncFileBackend

        # Parse branch from path (format: remote_url@branch)
        if "@" in path:
            remote_base, branch = path.rsplit("@", 1)
        else:
            remote_base = path
            branch = params.get("branch", "main")

        # Construct SSH URL
        remote_url = f"git@{remote_base}.git"

        connection_info = {
            "remote_url": remote_url,
            "path": Path.home() / ".f9_file_backend" / remote_base.replace("/", "_"),
            "branch": branch,
        }

        if "author_name" in params:
            connection_info["author_name"] = params["author_name"]
        if "author_email" in params:
            connection_info["author_email"] = params["author_email"]

        return GitSyncFileBackend(connection_info)

    def _create_git_https_backend(
        self,
        path: str,
        params: dict[str, Any],
    ) -> SyncFileBackend:
        """Create a GitSyncFileBackend from HTTPS URI.

        URI format: git+https://github.com/user/repo@branch?username=user&password=token&author_name=Bot&author_email=bot@example.com

        Args:
            path: Git remote URL (e.g., github.com/user/repo)
            params: Query parameters (username, password, author_name,
                author_email, branch)

        Returns:
            GitSyncFileBackend instance

        """
        from .git_backend import GitSyncFileBackend

        # Parse branch from path
        if "@" in path:
            remote_base, branch = path.rsplit("@", 1)
        else:
            remote_base = path
            branch = params.get("branch", "main")

        # Construct HTTPS URL with credentials
        remote_url = f"https://{remote_base}.git"
        if "username" in params:
            username = params["username"]
            password = params.get("password", "")
            remote_url = f"https://{username}:{password}@{remote_base}.git"

        connection_info = {
            "remote_url": remote_url,
            "path": Path.home() / ".f9_file_backend" / remote_base.replace("/", "_"),
            "branch": branch,
        }

        if "author_name" in params:
            connection_info["author_name"] = params["author_name"]
        if "author_email" in params:
            connection_info["author_email"] = params["author_email"]

        return GitSyncFileBackend(connection_info)

    def _create_openai_backend(
        self,
        path: str,
        params: dict[str, Any],
    ) -> FileBackend:
        """Create an OpenAIVectorStoreFileBackend from URI.

        URI format: openai+vector://vs_123456?api_key=sk_xxx&cache_ttl=5

        Args:
            path: Vector store ID (e.g., vs_123456)
            params: Query parameters (api_key, cache_ttl, purpose)

        Returns:
            OpenAIVectorStoreFileBackend instance

        """
        from .openai_backend import OpenAIVectorStoreFileBackend

        if not path.startswith("vs_"):
            msg = (
                f"Invalid vector store ID: '{path}' "
                f"(should start with 'vs_')"
            )
            raise ValueError(msg)

        connection_info = {"vector_store_id": path}

        if "api_key" in params:
            connection_info["api_key"] = params["api_key"]
        if "cache_ttl" in params:
            connection_info["cache_ttl"] = params["cache_ttl"]
        if "purpose" in params:
            connection_info["purpose"] = params["purpose"]

        return OpenAIVectorStoreFileBackend(connection_info)


# Global default factory instance
_default_factory = BackendFactory()


def resolve_backend(uri: str) -> FileBackend | SyncFileBackend:
    """Convenience function to resolve a backend from a URI using the default factory.

    Args:
        uri: URI string specifying the backend configuration

    Returns:
        FileBackend or SyncFileBackend instance

    Raises:
        ValueError: If URI scheme is unsupported
        FileBackendError: If backend creation fails

    Example:
        >>> backend = resolve_backend("file:///data/files")
        >>> backend = resolve_backend("git+ssh://github.com/user/repo@main")
        >>> backend = resolve_backend("openai+vector://vs_123?api_key=sk_xxx")

    """
    return _default_factory.resolve(uri)


def register_backend_factory(
    scheme: str,
    factory_func: Callable[[str, dict[str, Any]], Any],
) -> None:
    """Register a custom backend factory for a URI scheme.

    Args:
        scheme: URI scheme to register (e.g., "s3", "azure")
        factory_func: Callable that takes (path, params) and returns a FileBackend

    Example:
        >>> def my_s3_factory(path: str, params: dict) -> FileBackend:
        ...     return S3Backend(bucket=path, **params)
        >>> register_backend_factory("s3", my_s3_factory)

    """
    _default_factory.register(scheme, factory_func)
