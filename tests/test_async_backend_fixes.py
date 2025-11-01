"""Tests for async backend initialization fixes.

Tests cover:
- AsyncGitSyncFileBackend proper connection_info construction
- AsyncOpenAIVectorStoreFileBackend proper connection_info construction
- Path leading slash normalization
- Backwards compatibility and error handling

"""

from __future__ import annotations

import tempfile

import pytest

from f9_file_backend import (
    AsyncGitSyncFileBackend,
    AsyncLocalFileBackend,
    AsyncOpenAIVectorStoreFileBackend,
)


class TestAsyncGitSyncFileBackendInit:
    """Test AsyncGitSyncFileBackend initialization fixes."""

    def test_async_git_init_missing_root_raises_error(self) -> None:
        """Test AsyncGitSyncFileBackend raises error when root is missing."""
        with pytest.raises(ValueError, match="root parameter is required"):
            AsyncGitSyncFileBackend(
                root=None,
                remote_url="https://github.com/example/repo.git",
            )

    def test_async_git_init_missing_remote_url_raises_error(self) -> None:
        """Test AsyncGitSyncFileBackend raises error when remote_url is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="remote_url parameter is required"):
                AsyncGitSyncFileBackend(
                    root=tmpdir,
                    remote_url=None,
                )


class TestAsyncOpenAIVectorStoreBackendInit:
    """Test AsyncOpenAIVectorStoreFileBackend initialization fixes."""

    def test_async_openai_init_with_required_params(self) -> None:
        """Test AsyncOpenAIVectorStoreFileBackend with required parameters."""
        backend = AsyncOpenAIVectorStoreFileBackend(
            vector_store_id="vs_123456789",
            api_key="sk-test-key",
        )
        assert backend._sync_backend is not None
        assert backend._sync_backend._vector_store_id == "vs_123456789"

    def test_async_openai_init_required_params_only(self) -> None:
        """Test AsyncOpenAIVectorStoreFileBackend with only required params."""
        backend = AsyncOpenAIVectorStoreFileBackend(
            vector_store_id="vs_123456789",
            api_key="sk-test",
        )
        # Verify backend was created successfully
        assert backend._sync_backend is not None
        assert backend._sync_backend._vector_store_id == "vs_123456789"

    def test_async_openai_init_with_all_params(self) -> None:
        """Test AsyncOpenAIVectorStoreFileBackend initializes with all parameters."""
        backend = AsyncOpenAIVectorStoreFileBackend(
            vector_store_id="vs_123456789",
            api_key="sk-test-key",
            cache_ttl=600,
            purpose="custom",
        )
        config = backend._sync_backend._vector_store_id
        assert config == "vs_123456789"

    def test_async_openai_init_missing_vector_store_id_raises_error(self) -> None:
        """Test AsyncOpenAIVectorStoreFileBackend with missing vector_store_id."""
        with pytest.raises(ValueError, match="vector_store_id parameter is required"):
            AsyncOpenAIVectorStoreFileBackend(
                vector_store_id="",
                api_key="sk-test-key",
            )

    def test_async_openai_init_constructs_connection_info(self) -> None:
        """Test that connection_info is properly constructed from keyword args."""
        backend = AsyncOpenAIVectorStoreFileBackend(
            vector_store_id="vs_987654321",
            api_key="sk-another-key",
            cache_ttl=300,
        )
        # Verify the backend was created with proper parameters
        assert backend._sync_backend._vector_store_id == "vs_987654321"


class TestPathLeadingSlashNormalization:
    """Test path leading slash normalization for MCP protocol support."""

    @pytest.mark.asyncio
    async def test_create_with_leading_slash(self) -> None:
        """Test creating a file with leading slash in path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = AsyncLocalFileBackend(root=tmpdir)
            # Should treat /file.txt as file.txt (root-relative)
            await backend.create("/test.txt", data=b"content")
            # Verify file was created
            info = await backend.info("test.txt")
            assert info.size == 7

    @pytest.mark.asyncio
    async def test_read_with_leading_slash(self) -> None:
        """Test reading a file with leading slash in path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = AsyncLocalFileBackend(root=tmpdir)
            await backend.create("test.txt", data=b"hello")
            # Read with leading slash should work
            content = await backend.read("/test.txt")
            assert content == b"hello"

    @pytest.mark.asyncio
    async def test_delete_with_leading_slash(self) -> None:
        """Test deleting a file with leading slash in path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = AsyncLocalFileBackend(root=tmpdir)
            await backend.create("test.txt", data=b"content")
            # Delete with leading slash should work
            await backend.delete("/test.txt")
            # Verify file is gone
            from f9_file_backend import NotFoundError

            with pytest.raises(NotFoundError):
                await backend.info("test.txt")

    @pytest.mark.asyncio
    async def test_nested_path_with_leading_slash(self) -> None:
        """Test nested paths with leading slashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = AsyncLocalFileBackend(root=tmpdir)
            # Create nested structure - leading slash normalizes to root-relative
            await backend.create("/dir/subdir/file.txt", data=b"nested")
            # Read with leading slash should work and get same file
            content = await backend.read("/dir/subdir/file.txt")
            assert content == b"nested"
            # Read without leading slash should also work
            content2 = await backend.read("dir/subdir/file.txt")
            assert content2 == b"nested"

    @pytest.mark.asyncio
    async def test_multiple_leading_slashes(self) -> None:
        """Test that multiple leading slashes are normalized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = AsyncLocalFileBackend(root=tmpdir)
            # Multiple leading slashes should be treated the same
            await backend.create("///file.txt", data=b"content")
            content = await backend.read("/file.txt")
            assert content == b"content"

    @pytest.mark.asyncio
    async def test_leading_slash_does_not_escape_root(self) -> None:
        """Test that leading slashes still cannot escape root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = AsyncLocalFileBackend(root=tmpdir)
            # Trying to escape root with ../ should still fail
            from f9_file_backend import InvalidOperationError

            with pytest.raises(InvalidOperationError):
                await backend.create("/../etc/passwd", data=b"bad")
