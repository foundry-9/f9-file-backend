"""Comprehensive test suite for async file backend implementations.

Tests cover:
- Basic CRUD operations for all async backends
- Streaming operations with async iterators
- Checksums and integrity verification
- Concurrent operations using asyncio.gather
- Error handling and edge cases
- Performance characteristics

Requires pytest and pytest-asyncio.

"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from f9_file_backend import (
    AlreadyExistsError,
    AsyncLocalFileBackend,
    InvalidOperationError,
    NotFoundError,
)


class TestAsyncLocalFileBackend:
    """Test suite for AsyncLocalFileBackend."""

    @pytest.fixture
    def temp_root(self) -> Any:
        """Provide a temporary directory as backend root."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_create_and_read_binary(
        self,
        temp_root: Path,
    ) -> None:
        """Test creating and reading a binary file."""
        backend = AsyncLocalFileBackend(root=temp_root)
        data = b"Hello, async world!"

        await backend.create("test.bin", data=data)
        content = await backend.read("test.bin", binary=True)

        assert content == data

    @pytest.mark.asyncio
    async def test_create_and_read_text(
        self,
        temp_root: Path,
    ) -> None:
        """Test creating and reading a text file."""
        backend = AsyncLocalFileBackend(root=temp_root)
        data = "Hello, async text!"

        await backend.create("test.txt", data=data)
        content = await backend.read("test.txt", binary=False)

        assert content == data

    @pytest.mark.asyncio
    async def test_create_directory(
        self,
        temp_root: Path,
    ) -> None:
        """Test creating a directory."""
        backend = AsyncLocalFileBackend(root=temp_root)

        info = await backend.create("mydir", is_directory=True)

        assert info.is_dir
        assert (temp_root / "mydir").is_dir()

    @pytest.mark.asyncio
    async def test_update_file(
        self,
        temp_root: Path,
    ) -> None:
        """Test updating an existing file."""
        backend = AsyncLocalFileBackend(root=temp_root)
        initial_data = b"Initial"
        updated_data = b"Updated"

        await backend.create("test.txt", data=initial_data)
        await backend.update("test.txt", data=updated_data)

        content = await backend.read("test.txt")
        assert content == updated_data

    @pytest.mark.asyncio
    async def test_append_to_file(
        self,
        temp_root: Path,
    ) -> None:
        """Test appending to an existing file."""
        backend = AsyncLocalFileBackend(root=temp_root)
        initial = b"Hello, "
        appended = b"world!"

        await backend.create("test.txt", data=initial)
        await backend.update("test.txt", data=appended, append=True)

        content = await backend.read("test.txt")
        assert content == initial + appended

    @pytest.mark.asyncio
    async def test_delete_file(
        self,
        temp_root: Path,
    ) -> None:
        """Test deleting a file."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("test.txt", data=b"Content")
        await backend.delete("test.txt")

        with pytest.raises(NotFoundError):
            await backend.info("test.txt")

    @pytest.mark.asyncio
    async def test_delete_directory_recursive(
        self,
        temp_root: Path,
    ) -> None:
        """Test deleting a directory recursively."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("dir", is_directory=True)
        await backend.create("dir/file.txt", data=b"Content")
        await backend.delete("dir", recursive=True)

        with pytest.raises(NotFoundError):
            await backend.info("dir")

    @pytest.mark.asyncio
    async def test_info_metadata(
        self,
        temp_root: Path,
    ) -> None:
        """Test retrieving file metadata."""
        backend = AsyncLocalFileBackend(root=temp_root)
        data = b"Test content"

        await backend.create("test.txt", data=data)
        info = await backend.info("test.txt")

        assert str(info.path).endswith("test.txt")
        assert not info.is_dir
        assert info.size == len(data)
        assert info.created_at is not None
        assert info.modified_at is not None

    @pytest.mark.asyncio
    async def test_stream_read(
        self,
        temp_root: Path,
    ) -> None:
        """Test streaming file read with chunks."""
        backend = AsyncLocalFileBackend(root=temp_root)
        large_data = b"x" * 1000

        await backend.create("large.bin", data=large_data)

        chunks = []
        async for chunk in await backend.stream_read("large.bin", chunk_size=100):
            chunks.append(chunk)

        reconstructed = b"".join(chunks)
        assert reconstructed == large_data
        assert len(chunks) == 10

    @pytest.mark.asyncio
    async def test_stream_read_text(
        self,
        temp_root: Path,
    ) -> None:
        """Test streaming file read as text."""
        backend = AsyncLocalFileBackend(root=temp_root)
        text_data = "Hello, async streaming!" * 10

        await backend.create("text.txt", data=text_data)

        chunks = []
        async for chunk in await backend.stream_read(
            "text.txt",
            chunk_size=50,
            binary=False,
        ):
            chunks.append(chunk)

        reconstructed = "".join(chunks)
        assert reconstructed == text_data

    @pytest.mark.asyncio
    async def test_stream_write(
        self,
        temp_root: Path,
    ) -> None:
        """Test streaming file write from iterator."""
        backend = AsyncLocalFileBackend(root=temp_root)
        chunks = [b"Hello, ", b"async ", b"write!"]

        def chunk_iterator() -> Any:
            """Iterator that yields chunks."""
            yield from chunks

        await backend.stream_write("test.bin", chunk_source=chunk_iterator())

        content = await backend.read("test.bin")
        assert content == b"Hello, async write!"

    @pytest.mark.asyncio
    async def test_checksum_sha256(
        self,
        temp_root: Path,
    ) -> None:
        """Test computing SHA256 checksum."""
        backend = AsyncLocalFileBackend(root=temp_root)
        data = b"Test data for checksum"

        await backend.create("test.txt", data=data)
        checksum = await backend.checksum("test.txt", algorithm="sha256")

        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 is 256 bits = 64 hex chars

    @pytest.mark.asyncio
    async def test_checksum_md5(
        self,
        temp_root: Path,
    ) -> None:
        """Test computing MD5 checksum."""
        backend = AsyncLocalFileBackend(root=temp_root)
        data = b"Test data for checksum"

        await backend.create("test.txt", data=data)
        checksum = await backend.checksum("test.txt", algorithm="md5")

        assert isinstance(checksum, str)
        assert len(checksum) == 32  # MD5 is 128 bits = 32 hex chars

    @pytest.mark.asyncio
    async def test_checksum_stability(
        self,
        temp_root: Path,
    ) -> None:
        """Test that same file produces same checksum."""
        backend = AsyncLocalFileBackend(root=temp_root)
        data = b"Stable data"

        await backend.create("test.txt", data=data)
        checksum1 = await backend.checksum("test.txt")
        checksum2 = await backend.checksum("test.txt")

        assert checksum1 == checksum2

    @pytest.mark.asyncio
    async def test_checksum_many(
        self,
        temp_root: Path,
    ) -> None:
        """Test batch checksum computation."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("file1.txt", data=b"Content 1")
        await backend.create("file2.txt", data=b"Content 2")
        await backend.create("file3.txt", data=b"Content 3")

        checksums = await backend.checksum_many(
            ["file1.txt", "file2.txt", "file3.txt"],
        )

        assert len(checksums) == 3
        assert "file1.txt" in checksums
        assert "file2.txt" in checksums
        assert "file3.txt" in checksums

    @pytest.mark.asyncio
    async def test_checksum_many_with_missing(
        self,
        temp_root: Path,
    ) -> None:
        """Test batch checksum with missing files (should skip gracefully)."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("exists.txt", data=b"Content")

        checksums = await backend.checksum_many(
            ["exists.txt", "missing.txt"],
        )

        assert len(checksums) == 1
        assert "exists.txt" in checksums
        assert "missing.txt" not in checksums

    @pytest.mark.asyncio
    async def test_concurrent_reads(
        self,
        temp_root: Path,
    ) -> None:
        """Test concurrent read operations."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("file1.txt", data=b"Content 1")
        await backend.create("file2.txt", data=b"Content 2")
        await backend.create("file3.txt", data=b"Content 3")

        results = await asyncio.gather(
            backend.read("file1.txt"),
            backend.read("file2.txt"),
            backend.read("file3.txt"),
        )

        assert results == [b"Content 1", b"Content 2", b"Content 3"]

    @pytest.mark.asyncio
    async def test_concurrent_writes(
        self,
        temp_root: Path,
    ) -> None:
        """Test concurrent write operations."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await asyncio.gather(
            backend.create("file1.txt", data=b"Content 1"),
            backend.create("file2.txt", data=b"Content 2"),
            backend.create("file3.txt", data=b"Content 3"),
        )

        results = await asyncio.gather(
            backend.read("file1.txt"),
            backend.read("file2.txt"),
            backend.read("file3.txt"),
        )

        assert results == [b"Content 1", b"Content 2", b"Content 3"]

    @pytest.mark.asyncio
    async def test_concurrent_checksums(
        self,
        temp_root: Path,
    ) -> None:
        """Test concurrent checksum operations."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("file1.txt", data=b"Content 1")
        await backend.create("file2.txt", data=b"Content 2")

        checksums = await asyncio.gather(
            backend.checksum("file1.txt"),
            backend.checksum("file2.txt"),
        )

        assert len(checksums) == 2
        assert all(isinstance(c, str) for c in checksums)

    @pytest.mark.asyncio
    async def test_file_not_found_on_read(
        self,
        temp_root: Path,
    ) -> None:
        """Test NotFoundError on reading non-existent file."""
        backend = AsyncLocalFileBackend(root=temp_root)

        with pytest.raises(NotFoundError):
            await backend.read("missing.txt")

    @pytest.mark.asyncio
    async def test_file_not_found_on_delete(
        self,
        temp_root: Path,
    ) -> None:
        """Test NotFoundError on deleting non-existent file."""
        backend = AsyncLocalFileBackend(root=temp_root)

        with pytest.raises(NotFoundError):
            await backend.delete("missing.txt")

    @pytest.mark.asyncio
    async def test_cannot_read_directory(
        self,
        temp_root: Path,
    ) -> None:
        """Test that reading a directory raises InvalidOperationError."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("mydir", is_directory=True)

        with pytest.raises(InvalidOperationError):
            await backend.read("mydir")

    @pytest.mark.asyncio
    async def test_nested_file_creation(
        self,
        temp_root: Path,
    ) -> None:
        """Test creating files in nested directories."""
        backend = AsyncLocalFileBackend(root=temp_root)

        info = await backend.create(
            "deep/nested/path/file.txt",
            data=b"Nested content",
        )

        assert str(info.path).endswith("deep/nested/path/file.txt")
        assert (temp_root / "deep" / "nested" / "path" / "file.txt").exists()

    @pytest.mark.asyncio
    async def test_overwrite_file(
        self,
        temp_root: Path,
    ) -> None:
        """Test overwriting an existing file."""
        backend = AsyncLocalFileBackend(root=temp_root)

        await backend.create("file.txt", data=b"Original")

        with pytest.raises(AlreadyExistsError):
            await backend.create("file.txt", data=b"New", overwrite=False)

        await backend.create(
            "file.txt",
            data=b"Overwritten",
            overwrite=True,
        )

        content = await backend.read("file.txt")
        assert content == b"Overwritten"

    @pytest.mark.asyncio
    async def test_root_property(
        self,
        temp_root: Path,
    ) -> None:
        """Test that root property returns correct path."""
        backend = AsyncLocalFileBackend(root=temp_root)

        assert backend.root == temp_root.resolve()

    @pytest.mark.asyncio
    async def test_large_file_streaming(
        self,
        temp_root: Path,
    ) -> None:
        """Test streaming large files efficiently."""
        backend = AsyncLocalFileBackend(root=temp_root)
        large_size = 1024 * 1024  # 1MB
        large_data = b"x" * large_size

        await backend.create("large.bin", data=large_data)

        chunk_count = 0
        total_size = 0
        async for chunk in await backend.stream_read("large.bin", chunk_size=65536):
            chunk_count += 1
            total_size += len(chunk)

        assert total_size == large_size
        assert chunk_count > 1  # Should be multiple chunks

    @pytest.mark.asyncio
    async def test_unicode_content(
        self,
        temp_root: Path,
    ) -> None:
        """Test handling Unicode content correctly."""
        backend = AsyncLocalFileBackend(root=temp_root)
        unicode_text = "Hello 世界 🚀 مرحبا"

        await backend.create("unicode.txt", data=unicode_text)
        content = await backend.read("unicode.txt", binary=False)

        assert content == unicode_text

    @pytest.mark.asyncio
    async def test_empty_file_creation(
        self,
        temp_root: Path,
    ) -> None:
        """Test creating an empty file."""
        backend = AsyncLocalFileBackend(root=temp_root)

        info = await backend.create("empty.txt")

        assert info.size == 0
        content = await backend.read("empty.txt")
        assert content == b""
