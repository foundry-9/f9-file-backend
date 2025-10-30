"""Shared utility functions for backend implementations.

This module provides common functionality used across multiple backend
implementations to reduce code duplication and ensure consistent behavior.

Key utilities:
- Checksum computation (file and bytes)
- Data type coercion (bytes, str, BinaryIO)
- Chunk accumulation for streaming operations
- Hasher factory for multiple algorithms

Example usage:
    >>> from f9_file_backend.utils import compute_checksum_from_file
    >>> checksum = compute_checksum_from_file(Path("data.txt"), algorithm="sha256")

    >>> from f9_file_backend.utils import coerce_to_bytes
    >>> data = coerce_to_bytes("Hello, world!")
    >>> assert isinstance(data, bytes)
"""

from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING, Any, BinaryIO

from .interfaces import DEFAULT_CHUNK_SIZE, ChecksumAlgorithm

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def get_hasher(algorithm: ChecksumAlgorithm) -> Any:
    """Get a hasher instance for the specified algorithm.

    Args:
        algorithm: The checksum algorithm to use ('md5', 'sha256', 'sha512', 'blake3')

    Returns:
        A hasher instance with update() and hexdigest() methods

    Raises:
        ImportError: If blake3 is requested but not installed.
        ValueError: If algorithm is not supported.

    """
    if algorithm == "blake3":
        try:
            import blake3
        except ImportError as exc:
            message = "blake3 is not installed. Install it with: pip install blake3"
            raise ImportError(message) from exc
        return blake3.blake3()
    elif algorithm in ("md5", "sha256", "sha512"):
        return hashlib.new(algorithm)
    else:
        message = f"Unsupported checksum algorithm: {algorithm}"
        raise ValueError(message)


def coerce_to_bytes(data: bytes | str | BinaryIO) -> bytes:
    """Coerce supported input types to raw bytes.

    Handles bytes, strings (UTF-8 encoded), and file-like objects.

    Args:
        data: Input data to coerce

    Returns:
        Raw bytes representation

    Raises:
        TypeError: If data type is not supported.

    """
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")

    # Handle file-like objects (includes io.BufferedIOBase and io.RawIOBase)
    if hasattr(data, "read"):
        # Read the data
        result = data.read()

        # Try to reset the stream position for seekable streams
        if hasattr(data, "seek"):
            try:
                data.seek(0)
            except (OSError, io.UnsupportedOperation):
                # Stream is not seekable, that's okay
                pass

        # Handle result that might be str, bytes, or bytearray
        if isinstance(result, str):
            return result.encode("utf-8")
        if isinstance(result, (bytes, bytearray)):
            return bytes(result)
        message = f"Unsupported stream payload type: {type(result).__name__}"
        raise TypeError(message)

    message = f"Unsupported data type: {type(data).__name__}"
    raise TypeError(message)


def accumulate_chunks(
    chunk_source: Iterator[bytes | str] | BinaryIO,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> bytes:
    """Accumulate chunks from iterator or file-like object into bytes.

    Handles both iterator-style chunk sources and file-like objects with read().
    Automatically encodes string chunks as UTF-8.

    Args:
        chunk_source: Source of chunks (iterator or file-like object)
        chunk_size: Size of chunks to read from file-like objects

    Returns:
        Complete accumulated bytes.

    """
    accumulated = io.BytesIO()
    if hasattr(chunk_source, "read"):
        # File-like object with read() method
        while True:
            chunk = chunk_source.read(chunk_size)
            if not chunk:
                break
            if isinstance(chunk, str):
                accumulated.write(chunk.encode("utf-8"))
            else:
                accumulated.write(chunk)
    else:
        # Iterator-based chunk source
        for chunk in chunk_source:
            if isinstance(chunk, str):
                accumulated.write(chunk.encode("utf-8"))
            else:
                accumulated.write(chunk)
    return accumulated.getvalue()


def compute_checksum_from_file(
    file_path: Path,
    algorithm: ChecksumAlgorithm = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute checksum of a file by reading in chunks.

    Args:
        file_path: Path to file to checksum
        algorithm: Checksum algorithm to use
        chunk_size: Size of chunks to read

    Returns:
        Hexadecimal checksum string.

    """
    hasher = get_hasher(algorithm)
    with open(file_path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_checksum_from_bytes(
    payload: bytes,
    algorithm: ChecksumAlgorithm = "sha256",
) -> str:
    """Compute checksum of binary payload.

    Args:
        payload: Binary data to checksum
        algorithm: Checksum algorithm to use

    Returns:
        Hexadecimal checksum string.

    """
    hasher = get_hasher(algorithm)
    hasher.update(payload)
    return hasher.hexdigest()
