"""Integration tests for streaming I/O operations with real backends."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from f9_file_backend import LocalFileBackend

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def integration_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a dedicated temporary root directory for the backend."""
    return tmp_path_factory.mktemp("streaming-integration")


@pytest.fixture
def backend(integration_root: Path) -> LocalFileBackend:
    """Provide a backend instance rooted at the integration directory."""
    return LocalFileBackend(root=integration_root)


class TestStreamReadIntegration:
    """Integration tests for stream_read with real files."""

    def test_stream_read_large_file_memory_efficient(
        self, backend: LocalFileBackend,
    ) -> None:
        """Verify streaming doesn't load entire large file into memory."""
        # Create a reasonably large file (10MB)
        chunk_size = 1024 * 1024  # 1MB chunks
        num_chunks = 10
        total_size = chunk_size * num_chunks

        # Create file by writing chunks
        data_chunks = [b"x" * chunk_size for _ in range(num_chunks)]

        def write_source():
            yield from data_chunks

        backend.stream_write("large.bin", chunk_source=write_source())

        # Now read it back in smaller chunks
        read_chunks = []
        for chunk in backend.stream_read("large.bin", chunk_size=256 * 1024):
            read_chunks.append(chunk)

        assert len(read_chunks) == 40  # 10 * 1MB / 256KB
        assert sum(len(c) for c in read_chunks) == total_size

    def test_stream_read_binary_vs_text_mode(
        self, backend: LocalFileBackend,
    ) -> None:
        """Verify stream_read correctly handles binary and text modes."""
        text_data = "Hello, world!\nSecond line\nThird line"
        backend.create("text.txt", data=text_data)

        # Read as binary
        binary_chunks = list(backend.stream_read("text.txt", chunk_size=10))
        binary_result = b"".join(binary_chunks)
        assert binary_result == text_data.encode("utf-8")

        # Read as text
        text_chunks = list(backend.stream_read("text.txt", chunk_size=10, binary=False))
        text_result = "".join(text_chunks)
        assert text_result == text_data


class TestStreamWriteIntegration:
    """Integration tests for stream_write with real files."""

    def test_stream_write_file_io_object(self, backend: LocalFileBackend) -> None:
        """Verify stream_write works with file-like objects."""
        source_data = b"test data from file object" * 100
        source_file = io.BytesIO(source_data)

        backend.stream_write("from_file.bin", chunk_source=source_file)
        result = backend.read("from_file.bin")
        assert result == source_data

    def test_stream_write_generator_expression(
        self, backend: LocalFileBackend,
    ) -> None:
        """Verify stream_write works with generator expressions."""
        chunks = [b"chunk " + str(i).encode() for i in range(100)]

        def gen():
            yield from chunks

        backend.stream_write("from_gen.bin", chunk_source=gen())
        result = backend.read("from_gen.bin")
        expected = b"".join(chunks)
        assert result == expected

    def test_stream_write_then_stream_read(
        self, backend: LocalFileBackend,
    ) -> None:
        """Verify data integrity through stream write and read cycle."""
        original = b"data to persist through streaming cycle" * 50

        # Write using stream
        def write_gen():
            for i in range(0, len(original), 512):
                yield original[i : i + 512]

        backend.stream_write("persist.bin", chunk_source=write_gen())

        # Read using stream
        read_chunks = list(backend.stream_read("persist.bin", chunk_size=512))
        result = b"".join(read_chunks)
        assert result == original


class TestStreamWithDirectories:
    """Integration tests for streaming with directory structures."""

    def test_stream_in_nested_directories(self, backend: LocalFileBackend) -> None:
        """Verify streaming works correctly in nested directory structures."""
        backend.create("data/level1/level2", is_directory=True)

        data = b"nested file content"

        def write_gen():
            yield data

        backend.stream_write(
            "data/level1/level2/file.txt", chunk_source=write_gen(),
        )

        read_chunks = list(
            backend.stream_read("data/level1/level2/file.txt", chunk_size=4),
        )
        result = b"".join(read_chunks)
        assert result == data

    def test_stream_multiple_files_same_directory(
        self, backend: LocalFileBackend,
    ) -> None:
        """Verify streaming works for multiple files in same directory."""
        backend.create("files", is_directory=True)

        for i in range(5):
            data = f"file {i} content".encode() * 10

            def write_gen(d=data):
                yield d

            backend.stream_write(f"files/file{i}.txt", chunk_source=write_gen())

        # Verify all files
        for i in range(5):
            read_chunks = list(backend.stream_read(f"files/file{i}.txt"))
            result = b"".join(read_chunks)
            expected = f"file {i} content".encode() * 10
            assert result == expected


class TestStreamChunkSizes:
    """Integration tests for various chunk sizes."""

    @pytest.mark.parametrize("chunk_size", [1, 64, 512, 8192, 65536])
    def test_stream_read_various_chunk_sizes(
        self, backend: LocalFileBackend, chunk_size: int,
    ) -> None:
        """Verify stream_read works correctly with various chunk sizes."""
        data = b"x" * 10000
        backend.create("test.bin", data=data)

        chunks = list(backend.stream_read("test.bin", chunk_size=chunk_size))
        result = b"".join(chunks)
        assert result == data

    @pytest.mark.parametrize("chunk_size", [1, 64, 512, 8192, 65536])
    def test_stream_write_various_chunk_sizes(
        self, backend: LocalFileBackend, chunk_size: int,
    ) -> None:
        """Verify stream_write works correctly with various chunk sizes."""
        original = b"x" * 10000

        def write_gen():
            for i in range(0, len(original), chunk_size):
                yield original[i : i + chunk_size]

        backend.stream_write("test.bin", chunk_source=write_gen())
        result = backend.read("test.bin")
        assert result == original


class TestStreamUnicodeHandling:
    """Integration tests for Unicode and text encoding."""

    def test_stream_read_unicode_text(self, backend: LocalFileBackend) -> None:
        """Verify stream_read correctly handles Unicode text."""
        unicode_data = "Hello 世界 🌍 مرحبا мир"
        backend.create("unicode.txt", data=unicode_data)

        chunks = list(backend.stream_read("unicode.txt", chunk_size=10, binary=False))
        result = "".join(chunks)
        assert result == unicode_data

    def test_stream_write_unicode_text(self, backend: LocalFileBackend) -> None:
        """Verify stream_write correctly handles Unicode text."""
        unicode_data = "Здравствуй мир 😀 🎉"

        def write_gen():
            yield unicode_data

        backend.stream_write("unicode_out.txt", chunk_source=write_gen())
        result = backend.read("unicode_out.txt", binary=False)
        assert result == unicode_data
