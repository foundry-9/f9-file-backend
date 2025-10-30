"""Unit tests for f9_file_backend.utils module."""

from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from f9_file_backend.utils import (
    accumulate_chunks,
    coerce_to_bytes,
    compute_checksum_from_bytes,
    compute_checksum_from_file,
    get_hasher,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestGetHasher:
    """Tests for get_hasher function."""

    def test_get_hasher_md5(self) -> None:
        """Test MD5 hasher creation."""
        hasher = get_hasher("md5")
        hasher.update(b"test")
        assert hasher.hexdigest() == "098f6bcd4621d373cade4e832627b4f6"

    def test_get_hasher_sha256(self) -> None:
        """Test SHA256 hasher creation."""
        hasher = get_hasher("sha256")
        hasher.update(b"test")
        # Verify it has the expected length for SHA256 (64 hex chars)
        result = hasher.hexdigest()
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_get_hasher_sha512(self) -> None:
        """Test SHA512 hasher creation."""
        hasher = get_hasher("sha512")
        hasher.update(b"test")
        # Just verify it has the expected method and works
        result = hasher.hexdigest()
        assert len(result) == 128  # SHA512 produces 128 hex characters

    def test_get_hasher_blake3(self) -> None:
        """Test BLAKE3 hasher creation."""
        try:
            import blake3  # noqa: F401
        except ImportError:
            pytest.skip("blake3 not installed")

        hasher = get_hasher("blake3")
        hasher.update(b"test")
        result = hasher.hexdigest()
        assert len(result) == 64  # BLAKE3 produces 64 hex characters

    def test_get_hasher_blake3_not_installed(self) -> None:
        """Test BLAKE3 hasher with missing package."""
        # Temporarily hide blake3 module
        original_modules = sys.modules.copy()
        try:
            sys.modules["blake3"] = None  # type: ignore
            with patch.dict(sys.modules, {"blake3": None}):
                with pytest.raises(ImportError, match="blake3 is not installed"):
                    get_hasher("blake3")
        finally:
            # Restore modules
            sys.modules.update(original_modules)

    def test_get_hasher_invalid_algorithm(self) -> None:
        """Test invalid algorithm raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported checksum algorithm"):
            get_hasher("invalid_algo")  # type: ignore


class TestCoerceToBytes:
    """Tests for coerce_to_bytes function."""

    def test_coerce_to_bytes_from_bytes(self) -> None:
        """Test coercion from bytes returns unchanged."""
        data = b"test data"
        result = coerce_to_bytes(data)
        assert result == data
        assert result is data  # Should be the same object

    def test_coerce_to_bytes_from_str(self) -> None:
        """Test coercion from string encodes to UTF-8."""
        data = "test data"
        result = coerce_to_bytes(data)
        assert result == b"test data"

    def test_coerce_to_bytes_from_str_unicode(self) -> None:
        """Test coercion from unicode string."""
        data = "Hello, 世界! 🎉"
        result = coerce_to_bytes(data)
        assert result == data.encode("utf-8")

    def test_coerce_to_bytes_from_buffered_io(self) -> None:
        """Test coercion from BufferedIOBase (e.g., BytesIO)."""
        data = io.BytesIO(b"test data")
        result = coerce_to_bytes(data)
        assert result == b"test data"

    def test_coerce_to_bytes_from_raw_io(self) -> None:
        """Test coercion from RawIOBase."""
        # Create a mock that behaves like RawIOBase
        mock_io = Mock(spec=io.RawIOBase)
        mock_io.read.return_value = b"test data"
        result = coerce_to_bytes(mock_io)
        assert result == b"test data"

    def test_coerce_to_bytes_from_duck_typed_io(self) -> None:
        """Test coercion from duck-typed file-like object."""
        data = io.StringIO("test data")
        result = coerce_to_bytes(data)
        assert result == b"test data"

    def test_coerce_to_bytes_from_duck_typed_binary_io(self) -> None:
        """Test coercion from duck-typed binary file-like object."""
        data = io.BytesIO(b"test data")
        result = coerce_to_bytes(data)
        assert result == b"test data"

    def test_coerce_to_bytes_seekable_stream_reset(self) -> None:
        """Test that seekable streams are reset after reading."""
        data = io.BytesIO(b"test data")
        result = coerce_to_bytes(data)
        # The stream should be reset to beginning after reading
        assert result == b"test data"
        # Verify the stream was seeked
        assert data.tell() == 0

    def test_coerce_to_bytes_from_duck_typed_bytearray(self) -> None:
        """Test coercion from duck-typed file returning bytearray."""
        mock_io = Mock()
        mock_io.read.return_value = bytearray(b"test data")
        mock_io.seek = Mock()
        result = coerce_to_bytes(mock_io)
        assert result == b"test data"
        assert isinstance(result, bytes)

    def test_coerce_to_bytes_unsupported_type(self) -> None:
        """Test unsupported type raises TypeError."""
        with pytest.raises(TypeError, match="Unsupported data type"):
            coerce_to_bytes(12345)  # type: ignore

    def test_coerce_to_bytes_stream_with_unsupported_content(self) -> None:
        """Test stream that returns unsupported type raises TypeError."""
        mock_io = Mock()
        mock_io.read.return_value = 12345  # Unsupported return type
        with pytest.raises(TypeError, match="Unsupported stream payload type"):
            coerce_to_bytes(mock_io)


class TestAccumulateChunks:
    """Tests for accumulate_chunks function."""

    def test_accumulate_chunks_from_iterator(self) -> None:
        """Test accumulation from iterator of bytes."""
        chunks = [b"hello", b" ", b"world"]
        result = accumulate_chunks(iter(chunks))
        assert result == b"hello world"

    def test_accumulate_chunks_from_file_like(self) -> None:
        """Test accumulation from file-like object."""
        data = io.BytesIO(b"hello world")
        result = accumulate_chunks(data, chunk_size=5)
        assert result == b"hello world"

    def test_accumulate_chunks_mixed_str_bytes(self) -> None:
        """Test accumulation with mixed string and bytes chunks."""
        chunks = [b"hello", " ", b"world"]
        result = accumulate_chunks(iter(chunks))
        assert result == b"hello world"

    def test_accumulate_chunks_from_string_iterator(self) -> None:
        """Test accumulation from iterator of strings."""
        chunks = ["hello", " ", "world"]
        result = accumulate_chunks(iter(chunks))
        assert result == b"hello world"

    def test_accumulate_chunks_empty_iterator(self) -> None:
        """Test accumulation from empty iterator."""
        chunks: list[bytes] = []
        result = accumulate_chunks(iter(chunks))
        assert result == b""

    def test_accumulate_chunks_empty_file(self) -> None:
        """Test accumulation from empty file."""
        data = io.BytesIO(b"")
        result = accumulate_chunks(data)
        assert result == b""

    def test_accumulate_chunks_unicode_strings(self) -> None:
        """Test accumulation with unicode strings."""
        chunks = ["Hello, ", "世界", "! 🎉"]
        result = accumulate_chunks(iter(chunks))
        assert result == "Hello, 世界! 🎉".encode()

    def test_accumulate_chunks_custom_chunk_size(self) -> None:
        """Test accumulation with custom chunk size."""
        data = io.BytesIO(b"a" * 100)
        result = accumulate_chunks(data, chunk_size=10)
        assert result == b"a" * 100


class TestComputeChecksumFromBytes:
    """Tests for compute_checksum_from_bytes function."""

    def test_compute_checksum_from_bytes_sha256(self) -> None:
        """Test checksum computation with SHA256."""
        data = b"test data"
        result = compute_checksum_from_bytes(data, algorithm="sha256")
        # Verify by computing independently
        hasher = get_hasher("sha256")
        hasher.update(data)
        assert result == hasher.hexdigest()

    def test_compute_checksum_from_bytes_md5(self) -> None:
        """Test checksum computation with MD5."""
        data = b"test data"
        result = compute_checksum_from_bytes(data, algorithm="md5")
        assert result == "eb733a00c0c9d336e65691a37ab54293"

    def test_compute_checksum_from_bytes_empty(self) -> None:
        """Test checksum of empty data."""
        data = b""
        result = compute_checksum_from_bytes(data, algorithm="sha256")
        # Empty string SHA256
        expected = get_hasher("sha256")
        expected.update(b"")
        assert result == expected.hexdigest()

    def test_compute_checksum_from_bytes_large_data(self) -> None:
        """Test checksum of large data."""
        data = b"x" * 10_000_000  # 10MB
        result = compute_checksum_from_bytes(data, algorithm="sha256")
        # Just verify it completes and returns a valid hex string
        assert len(result) == 64  # SHA256 hex is 64 chars
        assert all(c in "0123456789abcdef" for c in result)


class TestComputeChecksumFromFile:
    """Tests for compute_checksum_from_file function."""

    def test_compute_checksum_from_file_sha256(self, tmp_path: Path) -> None:
        """Test file checksum computation with SHA256."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test data")
        result = compute_checksum_from_file(test_file, algorithm="sha256")
        # Verify by computing independently
        hasher = get_hasher("sha256")
        hasher.update(b"test data")
        assert result == hasher.hexdigest()

    def test_compute_checksum_from_file_md5(self, tmp_path: Path) -> None:
        """Test file checksum computation with MD5."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test data")
        result = compute_checksum_from_file(test_file, algorithm="md5")
        assert result == "eb733a00c0c9d336e65691a37ab54293"

    def test_compute_checksum_from_file_empty(self, tmp_path: Path) -> None:
        """Test checksum of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")
        result = compute_checksum_from_file(test_file, algorithm="sha256")
        expected = get_hasher("sha256")
        expected.update(b"")
        assert result == expected.hexdigest()

    def test_compute_checksum_from_file_large(self, tmp_path: Path) -> None:
        """Test checksum of large file."""
        test_file = tmp_path / "large.bin"
        # Write 10MB in chunks
        with open(test_file, "wb") as f:
            for _ in range(1000):
                f.write(b"x" * 10_000)
        result = compute_checksum_from_file(test_file, algorithm="sha256")
        # Just verify it completes and returns a valid hex string
        assert len(result) == 64  # SHA256 hex is 64 chars
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_checksum_from_file_custom_chunk_size(
        self,
        tmp_path: Path,
    ) -> None:
        """Test file checksum with custom chunk size."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test data")
        result = compute_checksum_from_file(
            test_file,
            algorithm="sha256",
            chunk_size=2,  # Very small chunk size
        )
        # Verify it matches normal computation
        hasher = get_hasher("sha256")
        hasher.update(b"test data")
        assert result == hasher.hexdigest()

    def test_compute_checksum_from_file_missing(self, tmp_path: Path) -> None:
        """Test checksum of non-existent file raises error."""
        test_file = tmp_path / "missing.txt"
        with pytest.raises(FileNotFoundError):
            compute_checksum_from_file(test_file)
