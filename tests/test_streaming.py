"""Tests covering streaming I/O operations for all backends."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from f9_file_backend import (
    AlreadyExistsError,
    InvalidOperationError,
    LocalFileBackend,
    NotFoundError,
)


@pytest.fixture
def backend(tmp_path: Path) -> LocalFileBackend:
    """Provide a backend instance scoped to a temporary directory."""
    return LocalFileBackend(root=tmp_path)


class TestStreamRead:
    """Tests for stream_read functionality."""

    def test_stream_read_binary_chunks(self, backend: LocalFileBackend) -> None:
        """Ensure stream_read yields binary chunks correctly."""
        data = b"hello world" * 100
        backend.create("large.bin", data=data)

        chunks = list(backend.stream_read("large.bin", chunk_size=256))
        assert len(chunks) > 1
        assert all(isinstance(chunk, bytes) for chunk in chunks)
        assert b"".join(chunks) == data

    def test_stream_read_text_chunks(self, backend: LocalFileBackend) -> None:
        """Ensure stream_read yields text chunks when binary=False."""
        data = "hello world" * 100
        backend.create("large.txt", data=data)

        chunks = list(backend.stream_read("large.txt", chunk_size=256, binary=False))
        assert len(chunks) > 1
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert "".join(chunks) == data

    def test_stream_read_custom_chunk_size(self, backend: LocalFileBackend) -> None:
        """Verify custom chunk sizes are respected."""
        data = b"x" * 1000
        backend.create("file.bin", data=data)

        chunks = list(backend.stream_read("file.bin", chunk_size=100))
        assert len(chunks) == 10
        assert all(len(chunk) == 100 for chunk in chunks)

    def test_stream_read_small_file(self, backend: LocalFileBackend) -> None:
        """Ensure small files are handled correctly."""
        data = b"small"
        backend.create("small.bin", data=data)

        chunks = list(backend.stream_read("small.bin", chunk_size=100))
        assert len(chunks) == 1
        assert chunks[0] == data

    def test_stream_read_empty_file(self, backend: LocalFileBackend) -> None:
        """Ensure empty files yield no chunks."""
        backend.create("empty.txt", data=b"")

        chunks = list(backend.stream_read("empty.txt"))
        assert len(chunks) == 0

    def test_stream_read_missing_file_raises(self, backend: LocalFileBackend) -> None:
        """Reading a missing file should raise NotFoundError."""
        with pytest.raises(NotFoundError):
            list(backend.stream_read("missing.txt"))

    def test_stream_read_directory_raises(self, backend: LocalFileBackend) -> None:
        """Reading a directory should raise InvalidOperationError."""
        backend.create("dir", is_directory=True)
        with pytest.raises(InvalidOperationError):
            list(backend.stream_read("dir"))


class TestStreamWrite:
    """Tests for stream_write functionality."""

    def test_stream_write_from_iterator_binary(
        self, backend: LocalFileBackend,
    ) -> None:
        """Ensure stream_write correctly writes from a binary iterator."""
        chunks = [b"hello ", b"world", b"!"]

        def chunk_source():
            yield from chunks

        backend.stream_write("output.txt", chunk_source=chunk_source())
        assert backend.read("output.txt") == b"hello world!"

    def test_stream_write_from_iterator_text(self, backend: LocalFileBackend) -> None:
        """Ensure stream_write correctly writes from a text iterator."""
        chunks = ["hello ", "world", "!"]

        def chunk_source():
            yield from chunks

        backend.stream_write("output.txt", chunk_source=chunk_source())
        assert backend.read("output.txt", binary=False) == "hello world!"

    def test_stream_write_from_binary_io(self, backend: LocalFileBackend) -> None:
        """Ensure stream_write correctly writes from a BinaryIO object."""
        data = b"test data from BytesIO"
        source = io.BytesIO(data)

        backend.stream_write("output.txt", chunk_source=source, chunk_size=5)
        assert backend.read("output.txt") == data

    def test_stream_write_mixed_chunks(self, backend: LocalFileBackend) -> None:
        """Ensure stream_write handles mixed bytes and str chunks."""
        def chunk_source():
            yield b"binary "
            yield "text"
            yield b" more"

        backend.stream_write("output.txt", chunk_source=chunk_source())
        assert backend.read("output.txt") == b"binary text more"

    def test_stream_write_overwrite_false_raises(
        self, backend: LocalFileBackend,
    ) -> None:
        """stream_write without overwrite should raise if file exists."""
        backend.create("existing.txt", data="original")

        def chunk_source():
            yield b"new"

        with pytest.raises(AlreadyExistsError):
            backend.stream_write("existing.txt", chunk_source=chunk_source())

    def test_stream_write_overwrite_true_succeeds(
        self, backend: LocalFileBackend,
    ) -> None:
        """stream_write with overwrite should replace existing file."""
        backend.create("existing.txt", data="original")

        def chunk_source():
            yield b"replaced"

        backend.stream_write("existing.txt", chunk_source=chunk_source(), overwrite=True)
        assert backend.read("existing.txt") == b"replaced"

    def test_stream_write_creates_parent_directories(
        self, backend: LocalFileBackend,
    ) -> None:
        """stream_write should create parent directories as needed."""
        def chunk_source():
            yield b"nested file"

        backend.stream_write("dir/subdir/file.txt", chunk_source=chunk_source())
        assert backend.read("dir/subdir/file.txt") == b"nested file"

    def test_stream_write_cannot_overwrite_directory_with_file(
        self, backend: LocalFileBackend,
    ) -> None:
        """stream_write should raise when trying to overwrite directory."""
        backend.create("dir", is_directory=True)

        def chunk_source():
            yield b"data"

        with pytest.raises(InvalidOperationError):
            backend.stream_write("dir", chunk_source=chunk_source(), overwrite=True)

    def test_stream_write_large_file(self, backend: LocalFileBackend) -> None:
        """Ensure stream_write efficiently handles large files."""
        chunk_size = 1024
        num_chunks = 100
        data = b"x" * chunk_size * num_chunks

        def chunk_source():
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

        backend.stream_write("large.bin", chunk_source=chunk_source())
        assert backend.read("large.bin") == data

    def test_stream_write_returns_file_info(
        self, backend: LocalFileBackend,
    ) -> None:
        """stream_write should return FileInfo with correct metadata."""
        def chunk_source():
            yield b"test"

        info = backend.stream_write("output.txt", chunk_source=chunk_source())
        assert info.path.name == "output.txt"
        assert not info.is_dir
        assert info.size == 4


class TestStreamIntegration:
    """Integration tests for stream read and write together."""

    def test_stream_roundtrip_binary(self, backend: LocalFileBackend) -> None:
        """Ensure data is preserved through stream write and read."""
        original_data = b"test data" * 1000
        backend.create("original.bin", data=original_data)

        # Stream read then write
        def chunk_source():
            for chunk in backend.stream_read("original.bin", chunk_size=256):
                yield chunk

        backend.stream_write("copy.bin", chunk_source=chunk_source())
        assert backend.read("copy.bin") == original_data

    def test_stream_roundtrip_text(self, backend: LocalFileBackend) -> None:
        """Ensure text data is preserved through stream write and read."""
        original_data = "hello world" * 100
        backend.create("original.txt", data=original_data)

        # Stream read then write
        def chunk_source():
            for chunk in backend.stream_read("original.txt", chunk_size=256, binary=False):
                yield chunk

        backend.stream_write("copy.txt", chunk_source=chunk_source())
        assert backend.read("copy.txt", binary=False) == original_data
