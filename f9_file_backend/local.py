"""Local filesystem backend implementation of FileBackend.

This module provides direct filesystem access for file storage operations.
All files are stored in a root directory with path traversal protection.

Key Features:
    - Direct filesystem access with optimal performance
    - Symlink resolution with traversal prevention
    - Large file support via streaming operations
    - Atomic file operations
    - Directory creation and removal

Path Validation:
    LocalFileBackend uses filesystem-aware path validation that resolves
    symlinks and relative paths. This ensures security against path traversal
    attacks while supporting complex path scenarios.

    All paths are validated to ensure they remain within the configured root
    directory. The _ensure_within_root() method handles this validation.

Storage Mechanism:
    Files are stored directly on the filesystem within the specified root
    directory. Directory structure is created automatically as needed.

Performance Characteristics:
    - Optimal for local file operations
    - No network latency
    - Filesystem I/O bound
    - Suitable for large files (streaming)

Example:

    >>> from f9_file_backend import LocalFileBackend
    >>> from pathlib import Path
    >>> backend = LocalFileBackend(root=Path("/data/files"))

    >>> # Create a file
    >>> backend.create("document.txt", data=b"Hello, world!")

    >>> # Read file contents
    >>> content = backend.read("document.txt")
    >>> content
    b'Hello, world!'

    >>> # Stream large files
    >>> with open("large.bin", "rb") as f:
    ...     backend.create("large_copy.bin", data=f)

    >>> # Get file info
    >>> info = backend.info("document.txt")
    >>> info.size
    13

    >>> # Compute checksums
    >>> checksum = backend.checksum("document.txt")

See Also:
    - FileBackend: Abstract interface
    - GitSyncFileBackend: Adds Git version control
    - OpenAIVectorStoreFileBackend: Remote storage alternative

"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from .interfaces import (
    DEFAULT_CHUNK_SIZE,
    ChecksumAlgorithm,
    FileBackend,
    FileInfo,
    FileType,
    InvalidOperationError,
    NotFoundError,
    PathLike,
)
from .locking import FileLock
from .utils import (
    accumulate_chunks,
    coerce_to_bytes,
    compute_checksum_from_file,
    detect_file_encoding,
)
from .validation import (
    LocalPathEntry,
    validate_entry_exists,
    validate_entry_not_exists,
    validate_is_file,
    validate_not_overwriting_directory_with_file,
    validate_not_overwriting_file_with_directory,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextlib import AbstractContextManager


class LocalFileBackend(FileBackend):
    """Backend implementation backed by the local filesystem."""

    def __init__(
        self,
        root: PathLike | None = None,
        *,
        create_root: bool = True,
    ) -> None:
        """Initialise the backend rooted at the given filesystem path."""
        base = Path(root or Path.cwd()).expanduser()
        self._root = base.resolve(strict=False)
        if create_root:
            self._root.mkdir(parents=True, exist_ok=True)
        elif not self._root.exists():
            raise NotFoundError(self._root)

        # Initialize lock for sync sessions
        lock_file = self._root / ".backend.lock"
        self._lock = FileLock(lock_file)

    @property
    def root(self) -> Path:
        """Absolute path used as the backend root."""
        return self._root

    def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a file or directory relative to the backend root."""
        target = self._ensure_within_root(path)
        entry = LocalPathEntry.from_path(target)

        target.parent.mkdir(parents=True, exist_ok=True)

        if is_directory:
            validate_not_overwriting_file_with_directory(entry, target)
            validate_entry_not_exists(entry, target, overwrite=overwrite)
            target.mkdir(exist_ok=True)
        else:
            validate_not_overwriting_directory_with_file(entry, target)
            validate_entry_not_exists(entry, target, overwrite=overwrite)
            payload = self._coerce_bytes(data) if data is not None else b""
            with target.open("wb") as fh:
                fh.write(payload)
        return self.info(target)

    def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Return file contents as bytes or text."""
        target = self._ensure_within_root(path)
        entry = LocalPathEntry.from_path(target)
        validate_entry_exists(entry, target)
        validate_is_file(entry, target)

        mode = "rb" if binary else "r"
        with target.open(mode) as fh:
            return fh.read()

    def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Write new data to an existing file."""
        target = self._ensure_within_root(path)
        entry = LocalPathEntry.from_path(target)
        validate_entry_exists(entry, target)
        validate_is_file(entry, target)

        payload = self._coerce_bytes(data)
        mode = "ab" if append else "wb"
        with target.open(mode) as fh:
            fh.write(payload)
        return self.info(target)

    def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Delete the specified path, optionally recursing into directories."""
        target = self._ensure_within_root(path)
        if not target.exists():
            raise NotFoundError(target)

        if target.is_dir():
            if any(target.iterdir()) and not recursive:
                raise InvalidOperationError.directory_not_empty(target)
            shutil.rmtree(target)
        else:
            target.unlink()

    def info(self, path: PathLike) -> FileInfo:
        """Return metadata about a file or directory."""
        target = self._ensure_within_root(path)
        if not target.exists():
            raise NotFoundError(target)

        stat_result = target.stat()

        # Determine file type
        if target.is_dir():
            file_type = FileType.DIRECTORY
        elif target.is_symlink():
            file_type = FileType.SYMLINK
        else:
            file_type = FileType.FILE

        # Detect encoding for text files
        encoding = None
        if not target.is_dir() and not target.is_symlink():
            encoding = detect_file_encoding(target)

        # Extract owner information (Unix-like systems)
        owner_uid = getattr(stat_result, "st_uid", None)
        owner_gid = getattr(stat_result, "st_gid", None)

        return FileInfo(
            path=target,
            is_dir=target.is_dir(),
            size=stat_result.st_size,
            created_at=_timestamp_to_datetime(stat_result.st_ctime),
            modified_at=_timestamp_to_datetime(stat_result.st_mtime),
            accessed_at=_timestamp_to_datetime(stat_result.st_atime),
            file_type=file_type,
            permissions=stat_result.st_mode,
            owner_uid=owner_uid,
            owner_gid=owner_gid,
            encoding=encoding,
        )

    def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        binary: bool = True,
    ) -> Iterator[bytes | str]:
        """Stream file contents in chunks."""
        target = self._ensure_within_root(path)
        entry = LocalPathEntry.from_path(target)
        validate_entry_exists(entry, target)
        validate_is_file(entry, target)

        mode = "rb" if binary else "r"
        with target.open(mode) as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def stream_write(
        self,
        path: PathLike,
        *,
        chunk_source: Iterator[bytes | str] | BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overwrite: bool = False,
    ) -> FileInfo:
        """Write file from stream."""
        target = self._ensure_within_root(path)
        entry = LocalPathEntry.from_path(target)
        validate_not_overwriting_directory_with_file(entry, target)
        validate_entry_not_exists(entry, target, overwrite=overwrite)

        target.parent.mkdir(parents=True, exist_ok=True)

        payload = accumulate_chunks(chunk_source, chunk_size)
        target.write_bytes(payload)
        return self.info(target)

    def checksum(
        self,
        path: PathLike,
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> str:
        """Compute a file checksum using the specified algorithm."""
        target = self._ensure_within_root(path)
        entry = LocalPathEntry.from_path(target)
        validate_entry_exists(entry, target)
        validate_is_file(entry, target)

        return self._compute_checksum(target, algorithm)

    def checksum_many(
        self,
        paths: list[PathLike],
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> dict[str, str]:
        """Compute checksums for multiple files in batch."""
        result = {}
        for path in paths:
            try:
                target = self._ensure_within_root(path)
                if target.exists() and not target.is_dir():
                    result[str(path)] = self._compute_checksum(target, algorithm)
            except (NotFoundError, InvalidOperationError):
                # Skip missing files and directories
                pass
        return result

    def glob(
        self,
        pattern: str,
        *,
        include_dirs: bool = False,
    ) -> list[Path]:
        """Find paths matching a glob pattern."""
        # Use pathlib's glob to find all matches within root
        matches = list(self._root.glob(pattern))

        results = []
        for match in matches:
            # Verify path is within root (already should be, but double-check)
            try:
                match.relative_to(self._root)
            except ValueError:
                continue

            # Filter based on type
            if not include_dirs and match.is_dir():
                continue

            # Return relative path from root
            results.append(match.relative_to(self._root))

        return sorted(results)

    def sync_session(
        self,
        *,
        timeout: float | None = None,
    ) -> AbstractContextManager[None]:
        """Create a context manager for atomic synchronisation operations.

        For LocalFileBackend, this provides a file-based lock to prevent
        concurrent access from multiple processes/threads.

        Args:
            timeout: Optional timeout in seconds for acquiring the lock.

        Returns:
            Context manager that acquires and releases the lock.

        Raises:
            TimeoutError: If the lock cannot be acquired within the timeout.

        """
        return self._lock.acquire(timeout=timeout)

    def _compute_checksum(
        self,
        file_path: Path,
        algorithm: ChecksumAlgorithm,
    ) -> str:
        """Compute the checksum of a file using the specified algorithm."""
        return compute_checksum_from_file(file_path, algorithm=algorithm)

    def _ensure_within_root(self, path: PathLike) -> Path:
        """Validate path stays within root directory with symlink resolution.

        This method implements filesystem-aware path validation that:
        1. Normalizes leading slashes to root-relative paths (supports MCP convention)
        2. Combines the path with root and resolves it (symlinks follow, .. resolved)
        3. Verifies the resolved path is still within the root directory
        4. Prevents path traversal attacks including symlink escapes

        Args:
            path: Potentially unsafe path from user input

        Returns:
            Absolute Path that is guaranteed to be within self._root

        Raises:
            InvalidOperationError: If path escapes root (including via symlinks)

        """
        # Normalize path to handle MCP root-relative convention (leading /)
        # Strip / only if path doesn't start with root (e.g., "/file" not absolute)
        path_str = str(path)
        root_str = str(self._root)

        # For MCP compat: "/file.txt" -> "file.txt", but don't modify already-resolved
        # absolute paths that start with root_str (e.g., "/tmp/root/file.txt")
        if path_str.startswith("/") and not path_str.startswith(root_str):
            path_str = path_str.lstrip("/") or "."

        # Resolve the full path: combines root with user path, follows symlinks,
        # resolves .. strict=False allows paths that don't exist yet (for create)
        candidate = (self._root / Path(path_str)).resolve(strict=False)

        # Verify the resolved path is still within root by trying to get relative path
        # This catches: ../../etc/passwd, symlink escapes
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            # Path is outside root - security violation
            raise InvalidOperationError.path_outside_root(candidate) from exc

        return candidate

    _coerce_bytes = staticmethod(coerce_to_bytes)


def _timestamp_to_datetime(timestamp: float) -> datetime:
    """Convert a POSIX timestamp to an aware datetime in UTC."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
