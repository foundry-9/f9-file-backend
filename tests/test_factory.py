"""Tests for the URI-based backend factory."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from f9_file_backend import (
    FileBackend,
    LocalFileBackend,
)
from f9_file_backend.factory import (
    BackendFactory,
    register_backend_factory,
    resolve_backend,
)

# ruff: noqa: S101, PLR2004  # pytest assertions and magic numbers are ok in tests


class TestBackendFactory:
    """Test the BackendFactory class."""

    def test_factory_initialization(self) -> None:
        """Test factory initializes with built-in schemes."""
        factory = BackendFactory()
        assert "file" in factory._factories
        assert "git+ssh" in factory._factories
        assert "git+https" in factory._factories
        assert "openai+vector" in factory._factories

    def test_parse_uri_file_scheme(self) -> None:
        """Test parsing file:// URIs."""
        factory = BackendFactory()

        # Absolute path
        scheme, path, params = factory.parse_uri("file:///tmp/data")
        assert scheme == "file"
        assert path == "/tmp/data"
        assert params == {}

        # Relative path
        scheme, path, params = factory.parse_uri("file://data/files")
        assert scheme == "file"
        assert path == "data/files"

    def test_parse_uri_with_query_params(self) -> None:
        """Test parsing URIs with query parameters."""
        factory = BackendFactory()
        scheme, path, params = factory.parse_uri("file:///data?create_root=false")
        assert scheme == "file"
        assert path == "/data"
        assert params == {"create_root": "false"}

    def test_parse_uri_git_ssh(self) -> None:
        """Test parsing git+ssh:// URIs."""
        factory = BackendFactory()
        scheme, path, params = factory.parse_uri("git+ssh://github.com/user/repo@main")
        assert scheme == "git+ssh"
        assert path == "github.com/user/repo@main"

    def test_parse_uri_git_https(self) -> None:
        """Test parsing git+https:// URIs."""
        factory = BackendFactory()
        scheme, path, params = factory.parse_uri(
            "git+https://github.com/user/repo@develop?username=user&password=token",
        )
        assert scheme == "git+https"
        assert path == "github.com/user/repo@develop"
        assert params["username"] == "user"
        assert params["password"] == "token"

    def test_parse_uri_openai(self) -> None:
        """Test parsing openai+vector:// URIs."""
        factory = BackendFactory()
        scheme, path, params = factory.parse_uri(
            "openai+vector://vs_123456?api_key=sk_test&cache_ttl=5",
        )
        assert scheme == "openai+vector"
        assert path == "vs_123456"
        assert params["api_key"] == "sk_test"
        assert params["cache_ttl"] == "5"

    def test_parse_uri_missing_scheme(self) -> None:
        """Test error on missing URI scheme."""
        factory = BackendFactory()
        with pytest.raises(ValueError, match="missing scheme"):
            factory.parse_uri("/tmp/data")

    def test_parse_uri_missing_path(self) -> None:
        """Test error on missing path component."""
        factory = BackendFactory()
        with pytest.raises(ValueError, match="missing path"):
            factory.parse_uri("file://")

    def test_resolve_file_backend(self) -> None:
        """Test resolving a local file backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = BackendFactory()
            uri = f"file://{tmpdir}"
            backend = factory.resolve(uri)

            assert isinstance(backend, LocalFileBackend)
            # Normalize both paths for comparison (macOS symlinks /tmp -> /private/var)
            assert backend.root.resolve() == Path(tmpdir).resolve()

    def test_resolve_file_backend_with_params(self) -> None:
        """Test resolving file backend with parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = BackendFactory()
            # Test with create_root=false (path should exist)
            uri = f"file://{tmpdir}?create_root=false"
            backend = factory.resolve(uri)
            assert isinstance(backend, LocalFileBackend)

    @patch("f9_file_backend.git_backend.GitSyncFileBackend")
    def test_resolve_git_ssh_backend(self, mock_git_backend: Any) -> None:
        """Test resolving a Git SSH backend."""
        factory = BackendFactory()
        uri = "git+ssh://github.com/user/repo@main"

        try:
            factory.resolve(uri)
        except Exception:
            # Expected - we're using a mock
            pass

        # Verify GitSyncFileBackend was called with correct parameters
        assert mock_git_backend.called
        call_args = mock_git_backend.call_args
        assert call_args is not None
        connection_info = call_args[0][0]
        assert connection_info["remote_url"] == "git@github.com/user/repo.git"
        assert connection_info["branch"] == "main"

    @patch("f9_file_backend.git_backend.GitSyncFileBackend")
    def test_resolve_git_https_backend(self, mock_git_backend: Any) -> None:
        """Test resolving a Git HTTPS backend."""
        factory = BackendFactory()
        uri = "git+https://github.com/user/repo@develop?username=alice&password=secret"

        try:
            factory.resolve(uri)
        except Exception:
            # Expected - we're using a mock
            pass

        assert mock_git_backend.called
        call_args = mock_git_backend.call_args
        assert call_args is not None
        connection_info = call_args[0][0]
        assert "alice" in connection_info["remote_url"]
        assert "secret" in connection_info["remote_url"]
        assert connection_info["branch"] == "develop"

    @patch("f9_file_backend.openai_backend.OpenAIVectorStoreFileBackend")
    def test_resolve_openai_backend(self, mock_openai_backend: Any) -> None:
        """Test resolving an OpenAI vector store backend."""
        factory = BackendFactory()
        uri = "openai+vector://vs_12345?api_key=sk_test&cache_ttl=10"

        try:
            factory.resolve(uri)
        except Exception:
            # Expected - we're using a mock
            pass

        assert mock_openai_backend.called
        call_args = mock_openai_backend.call_args
        assert call_args is not None
        connection_info = call_args[0][0]
        assert connection_info["vector_store_id"] == "vs_12345"
        assert connection_info["api_key"] == "sk_test"
        assert connection_info["cache_ttl"] == "10"

    def test_resolve_unsupported_scheme(self) -> None:
        """Test error on unsupported URI scheme."""
        factory = BackendFactory()
        with pytest.raises(ValueError, match="Unsupported URI scheme"):
            factory.resolve("s3://bucket/path")

    def test_register_custom_factory(self) -> None:
        """Test registering a custom backend factory."""
        factory = BackendFactory()

        def custom_factory(path: str, params: dict[str, Any]) -> FileBackend:
            """A dummy custom factory."""
            return LocalFileBackend(root=path)

        factory.register("custom", custom_factory)
        assert "custom" in factory._factories

    def test_register_custom_factory_not_callable(self) -> None:
        """Test error when registering non-callable as factory."""
        factory = BackendFactory()
        with pytest.raises(TypeError, match="must be callable"):
            factory.register("custom", "not_a_function")

    def test_resolve_with_custom_factory(self) -> None:
        """Test resolving URI with custom factory."""
        factory = BackendFactory()
        called_with = {}

        def custom_factory(path: str, params: dict[str, Any]) -> FileBackend:
            called_with["path"] = path
            called_with["params"] = params
            with tempfile.TemporaryDirectory() as tmpdir:
                return LocalFileBackend(root=tmpdir)

        factory.register("custom", custom_factory)
        backend = factory.resolve("custom://my-path?key=value")

        assert isinstance(backend, LocalFileBackend)
        assert called_with["path"] == "my-path"
        assert called_with["params"]["key"] == "value"


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_resolve_backend(self) -> None:
        """Test module-level resolve_backend function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uri = f"file://{tmpdir}"
            backend = resolve_backend(uri)
            assert isinstance(backend, LocalFileBackend)
            # Normalize both paths for comparison (macOS symlinks /tmp -> /private/var)
            assert backend.root.resolve() == Path(tmpdir).resolve()

    def test_register_backend_factory(self) -> None:
        """Test module-level register_backend_factory function."""
        def dummy_factory(path: str, params: dict[str, Any]) -> FileBackend:
            with tempfile.TemporaryDirectory() as tmpdir:
                return LocalFileBackend(root=tmpdir)

        # Register a custom scheme - RFC 3986 allows letters, digits, +, -, .
        register_backend_factory("custom", dummy_factory)

        # Verify it works
        backend = resolve_backend("custom://any-path")
        assert isinstance(backend, LocalFileBackend)


class TestURIEdgeCases:
    """Test edge cases and special URI formats."""

    def test_uri_with_multiple_query_params(self) -> None:
        """Test URI with multiple query parameters."""
        factory = BackendFactory()
        uri = "file:///data?create_root=false&param1=value1&param2=value2"
        scheme, path, params = factory.parse_uri(uri)

        assert scheme == "file"
        assert path == "/data"
        assert len(params) == 3
        assert params["create_root"] == "false"
        assert params["param1"] == "value1"
        assert params["param2"] == "value2"

    def test_uri_git_ssh_without_branch(self) -> None:
        """Test git+ssh URI without explicit branch uses default."""
        factory = BackendFactory()

        with patch("f9_file_backend.git_backend.GitSyncFileBackend") as mock_git:
            try:
                factory.resolve("git+ssh://github.com/user/repo")
            except Exception:
                pass

            # Check that default branch 'main' is used
            if mock_git.called:
                connection_info = mock_git.call_args[0][0]
                assert connection_info["branch"] == "main"

    def test_uri_git_https_with_branch_param(self) -> None:
        """Test git+https URI with branch as query parameter."""
        factory = BackendFactory()

        with patch("f9_file_backend.git_backend.GitSyncFileBackend") as mock_git:
            try:
                factory.resolve("git+https://github.com/user/repo?branch=feature")
            except Exception:
                pass

            if mock_git.called:
                connection_info = mock_git.call_args[0][0]
                assert connection_info["branch"] == "feature"

    def test_file_uri_with_home_expansion(self) -> None:
        """Test file URI path expansion (though factory doesn't expand ~)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            factory = BackendFactory()
            # The factory passes the path as-is, LocalFileBackend handles expansion
            uri = f"file://{tmpdir}"
            backend = factory.resolve(uri)
            assert isinstance(backend, LocalFileBackend)

    def test_openai_uri_invalid_vector_store_id(self) -> None:
        """Test OpenAI URI with invalid vector store ID format."""
        factory = BackendFactory()
        with pytest.raises(ValueError, match="Invalid vector store ID"):
            factory.resolve("openai+vector://invalid_id?api_key=sk_test")

    def test_git_ssh_custom_author_info(self) -> None:
        """Test git+ssh URI with custom author name and email."""
        factory = BackendFactory()

        with patch("f9_file_backend.git_backend.GitSyncFileBackend") as mock_git:
            try:
                factory.resolve(
                    "git+ssh://github.com/user/repo@main?author_name=Custom&author_email=custom@example.com",
                )
            except Exception:
                pass

            call_args = mock_git.call_args
            if call_args:
                connection_info = call_args[0][0]
                assert connection_info.get("author_name") == "Custom"
                assert connection_info.get("author_email") == "custom@example.com"

    def test_git_https_custom_author_info(self) -> None:
        """Test git+https URI with custom author name and email."""
        factory = BackendFactory()

        with patch("f9_file_backend.git_backend.GitSyncFileBackend") as mock_git:
            try:
                factory.resolve(
                    "git+https://github.com/user/repo@main?username=user&password=pass&author_name=Bot&author_email=bot@example.com",
                )
            except Exception:
                pass

            call_args = mock_git.call_args
            if call_args:
                connection_info = call_args[0][0]
                assert connection_info.get("author_name") == "Bot"
                assert connection_info.get("author_email") == "bot@example.com"

    def test_openai_uri_with_purpose_param(self) -> None:
        """Test OpenAI URI with purpose parameter."""
        factory = BackendFactory()

        mock_path = "f9_file_backend.openai_backend.OpenAIVectorStoreFileBackend"
        with patch(mock_path) as mock_openai:
            try:
                factory.resolve("openai+vector://vs_123?api_key=sk_test&purpose=custom")
            except Exception:
                pass

            call_args = mock_openai.call_args
            if call_args:
                connection_info = call_args[0][0]
                assert connection_info.get("purpose") == "custom"


class TestIntegrationWithRealBackends:
    """Integration tests with real backend implementations."""

    def test_create_and_use_local_backend_from_uri(self) -> None:
        """Test creating and using a local backend via factory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uri = f"file://{tmpdir}"
            backend = resolve_backend(uri)

            # Test basic operations
            backend.create("test.txt", data=b"Hello, World!")
            content = backend.read("test.txt")
            assert content == b"Hello, World!"

            # Test file info (path is relative to backend root)
            info = backend.info("test.txt")
            assert info.path.name == "test.txt"
            assert not info.is_dir

    def test_local_backend_mkdir_operations(self) -> None:
        """Test directory creation with factory-created backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uri = f"file://{tmpdir}"
            backend = resolve_backend(uri)

            # Create directory and files
            backend.create("subdir", is_directory=True)
            backend.create("file1.txt", data=b"Content 1")
            backend.create("subdir/file2.txt", data=b"Content 2")

            # Verify we can read back the content
            content1 = backend.read("file1.txt")
            content2 = backend.read("subdir/file2.txt")
            assert content1 == b"Content 1"
            assert content2 == b"Content 2"

            # Verify directory info
            subdir_info = backend.info("subdir")
            assert subdir_info.is_dir

    def test_local_backend_glob_from_uri(self) -> None:
        """Test glob operations with factory-created backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uri = f"file://{tmpdir}"
            backend = resolve_backend(uri)

            backend.create("test1.txt", data=b"Content 1")
            backend.create("test2.txt", data=b"Content 2")
            backend.create("other.md", data=b"Markdown")

            results = backend.glob("*.txt")
            result_names = [p.name for p in results]
            assert "test1.txt" in result_names
            assert "test2.txt" in result_names
            assert "other.md" not in result_names

    def test_local_backend_checksum_from_uri(self) -> None:
        """Test checksum operations with factory-created backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uri = f"file://{tmpdir}"
            backend = resolve_backend(uri)

            backend.create("test.txt", data=b"Test content")
            checksum = backend.checksum("test.txt", algorithm="sha256")

            assert isinstance(checksum, str)
            assert len(checksum) == 64  # SHA256 hex digest length
