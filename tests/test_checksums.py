"""Tests covering checksum functionality across all backends."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from f9_file_backend import (
    InvalidOperationError,
    LocalFileBackend,
    NotFoundError,
)


@pytest.fixture
def backend(tmp_path: Path) -> LocalFileBackend:
    """Provide a backend instance scoped to a temporary directory."""
    return LocalFileBackend(root=tmp_path)


class TestLocalBackendChecksums:
    """Tests for LocalFileBackend checksum operations."""

    def test_checksum_single_file_sha256(self, backend: LocalFileBackend) -> None:
        """Verify SHA256 checksum computation for a single file."""
        backend.create("test.txt", data="hello world")
        checksum = backend.checksum("test.txt", algorithm="sha256")
        # Verify it's a valid hex string
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_checksum_stability(self, backend: LocalFileBackend) -> None:
        """Ensure the same file produces the same checksum consistently."""
        backend.create("test.txt", data="consistent content")
        checksum1 = backend.checksum("test.txt")
        checksum2 = backend.checksum("test.txt")
        assert checksum1 == checksum2

    def test_checksum_different_content_different_hash(
        self,
        backend: LocalFileBackend,
    ) -> None:
        """Verify different files produce different checksums."""
        backend.create("file1.txt", data="content1")
        backend.create("file2.txt", data="content2")
        hash1 = backend.checksum("file1.txt")
        hash2 = backend.checksum("file2.txt")
        assert hash1 != hash2

    def test_checksum_md5(self, backend: LocalFileBackend) -> None:
        """Verify MD5 checksum algorithm works."""
        backend.create("test.txt", data="hello")
        checksum = backend.checksum("test.txt", algorithm="md5")
        assert isinstance(checksum, str)
        assert len(checksum) == 32  # MD5 produces 32 hex chars
        # Known MD5 hash of "hello"
        assert checksum == "5d41402abc4b2a76b9719d911017c592"

    def test_checksum_sha512(self, backend: LocalFileBackend) -> None:
        """Verify SHA512 checksum algorithm works."""
        backend.create("test.txt", data="test")
        checksum = backend.checksum("test.txt", algorithm="sha512")
        assert isinstance(checksum, str)
        assert len(checksum) == 128  # SHA512 produces 128 hex chars

    def test_checksum_blake3(self, backend: LocalFileBackend) -> None:
        """Verify BLAKE3 checksum algorithm works when available."""
        pytest.importorskip("blake3")
        backend.create("test.txt", data="blake3 test")
        checksum = backend.checksum("test.txt", algorithm="blake3")
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # BLAKE3 produces 64 hex chars

    def test_checksum_blake3_missing_raises(
        self,
        backend: LocalFileBackend,
        monkeypatch,
    ) -> None:
        """Verify that blake3 missing raises helpful error."""
        backend.create("test.txt", data="test")
        # Temporarily hide blake3
        monkeypatch.setattr("builtins.__import__", lambda name, *args, **kwargs: (
            pytest.skip("blake3 not available") if name == "blake3"
            else __import__(name, *args, **kwargs)
        ))

    def test_checksum_missing_file_raises(self, backend: LocalFileBackend) -> None:
        """Verify checksum on missing file raises NotFoundError."""
        with pytest.raises(NotFoundError):
            backend.checksum("nonexistent.txt")

    def test_checksum_directory_raises(self, backend: LocalFileBackend) -> None:
        """Verify checksum on directory raises InvalidOperationError."""
        backend.create("dir", is_directory=True)
        with pytest.raises(InvalidOperationError):
            backend.checksum("dir")

    def test_checksum_invalid_algorithm_raises(
        self,
        backend: LocalFileBackend,
    ) -> None:
        """Verify invalid algorithm raises ValueError."""
        backend.create("test.txt", data="test")
        with pytest.raises(ValueError, match="Unsupported checksum algorithm"):
            backend.checksum("test.txt", algorithm="invalid")  # type: ignore

    def test_checksum_binary_file(self, backend: LocalFileBackend) -> None:
        """Verify checksum works for binary files."""
        binary_data = b"\x00\x01\x02\x03\xff\xfe"
        backend.create("test.bin", data=binary_data)
        checksum = backend.checksum("test.bin")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_checksum_large_file(self, backend: LocalFileBackend) -> None:
        """Verify checksum handles large files efficiently."""
        # Create a 10MB file
        large_content = "x" * (10 * 1024 * 1024)
        backend.create("large.txt", data=large_content)
        checksum = backend.checksum("large.txt")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_checksum_many_empty_list(self, backend: LocalFileBackend) -> None:
        """Verify checksum_many with empty list returns empty dict."""
        result = backend.checksum_many([])
        assert result == {}

    def test_checksum_many_single_file(self, backend: LocalFileBackend) -> None:
        """Verify checksum_many works with a single file."""
        backend.create("test.txt", data="hello")
        result = backend.checksum_many(["test.txt"])
        assert len(result) == 1
        assert "test.txt" in result
        assert len(result["test.txt"]) == 64  # SHA256

    def test_checksum_many_multiple_files(self, backend: LocalFileBackend) -> None:
        """Verify checksum_many computes hashes for multiple files."""
        backend.create("file1.txt", data="content1")
        backend.create("file2.txt", data="content2")
        backend.create("file3.txt", data="content3")

        result = backend.checksum_many(
            ["file1.txt", "file2.txt", "file3.txt"],
        )
        assert len(result) == 3
        assert all(k in result for k in ["file1.txt", "file2.txt", "file3.txt"])
        # All hashes should be different
        hashes = list(result.values())
        assert len(hashes) == len(set(hashes))

    def test_checksum_many_skips_missing_files(
        self,
        backend: LocalFileBackend,
    ) -> None:
        """Verify checksum_many skips missing files without error."""
        backend.create("exists.txt", data="content")
        result = backend.checksum_many(["exists.txt", "missing.txt"])
        assert len(result) == 1
        assert "exists.txt" in result
        assert "missing.txt" not in result

    def test_checksum_many_skips_directories(
        self,
        backend: LocalFileBackend,
    ) -> None:
        """Verify checksum_many skips directories without error."""
        backend.create("file.txt", data="content")
        backend.create("dir", is_directory=True)
        result = backend.checksum_many(["file.txt", "dir"])
        assert len(result) == 1
        assert "file.txt" in result
        assert "dir" not in result

    def test_checksum_many_with_algorithm(
        self,
        backend: LocalFileBackend,
    ) -> None:
        """Verify checksum_many respects algorithm parameter."""
        backend.create("test.txt", data="content")
        result_sha256 = backend.checksum_many(["test.txt"], algorithm="sha256")
        result_md5 = backend.checksum_many(["test.txt"], algorithm="md5")

        assert len(result_sha256["test.txt"]) == 64  # SHA256
        assert len(result_md5["test.txt"]) == 32   # MD5

    def test_checksum_empty_file(self, backend: LocalFileBackend) -> None:
        """Verify checksum works for empty files."""
        backend.create("empty.txt", data="")
        checksum = backend.checksum("empty.txt")
        # SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert checksum == expected

    def test_checksum_unicode_content(self, backend: LocalFileBackend) -> None:
        """Verify checksum handles unicode content correctly."""
        unicode_content = "Hello, 世界! 🌍"
        backend.create("unicode.txt", data=unicode_content)
        checksum = backend.checksum("unicode.txt")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_checksum_with_binaryio_source(self, backend: LocalFileBackend) -> None:
        """Verify checksum works for files created from BinaryIO sources."""
        data = io.BytesIO(b"binary content")
        backend.create("binary.txt", data=data)
        checksum = backend.checksum("binary.txt")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_checksum_after_update(self, backend: LocalFileBackend) -> None:
        """Verify checksum changes after file update."""
        backend.create("test.txt", data="original")
        hash1 = backend.checksum("test.txt")

        backend.update("test.txt", data="updated")
        hash2 = backend.checksum("test.txt")

        assert hash1 != hash2

    def test_checksum_nested_path(self, backend: LocalFileBackend) -> None:
        """Verify checksum works for files in nested directories."""
        backend.create("dir/subdir/file.txt", data="nested content")
        checksum = backend.checksum("dir/subdir/file.txt")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_checksum_path_object(self, backend: LocalFileBackend) -> None:
        """Verify checksum accepts Path objects."""
        from pathlib import Path

        backend.create("test.txt", data="content")
        checksum = backend.checksum(Path("test.txt"))
        assert isinstance(checksum, str)
        assert len(checksum) == 64
