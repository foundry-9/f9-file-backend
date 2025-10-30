"""Asynchronous interfaces for file backend implementations.

This module provides async/await versions of the synchronous FileBackend
and SyncFileBackend interfaces, enabling non-blocking file operations
across all backends.

Key Features:
    - Fully async method signatures using Awaitable types
    - AsyncIterator for streaming operations
    - Drop-in replacements for sync backends
    - Compatible with asyncio and other async frameworks
    - Support for concurrent operations via asyncio.gather()

Architecture:
    AsyncFileBackend provides the core async operations that all backends
    must implement. AsyncSyncFileBackend extends this with bidirectional
    sync capabilities for backends that support remote synchronization.

    All async methods should avoid blocking the event loop and are typically
    implemented using:
    - asyncio.to_thread() for CPU-bound or blocking I/O operations
    - Native async libraries (aiofiles, httpx) where available
    - asyncio.Lock for thread-safe operations

Example:

    >>> import asyncio
    >>> from f9_file_backend import AsyncLocalFileBackend
    >>> from pathlib import Path
    >>>
    >>> async def main():
    ...     backend = AsyncLocalFileBackend(root=Path("/data/files"))
    ...
    ...     # Create a file asynchronously
    ...     info = await backend.create("document.txt", data=b"Hello!")
    ...
    ...     # Read file contents asynchronously
    ...     content = await backend.read("document.txt")
    ...
    ...     # Stream large files efficiently
    ...     async for chunk in backend.stream_read("large.bin"):
    ...         process(chunk)
    ...
    ...     # Concurrent operations
    ...     results = await asyncio.gather(
    ...         backend.read("file1.txt"),
    ...         backend.read("file2.txt"),
    ...         backend.read("file3.txt"),
    ...     )
    ...
    >>> asyncio.run(main())

See Also:
    - FileBackend: Synchronous interface
    - AsyncLocalFileBackend: Async local filesystem backend
    - AsyncGitSyncFileBackend: Async Git-backed storage
    - AsyncOpenAIVectorStoreFileBackend: Async OpenAI vector store integration

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, BinaryIO

from .interfaces import (
    ChecksumAlgorithm,
    FileBackendError,
    FileInfo,
    PathLike,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


class AsyncFileBackend(ABC):
    """Asynchronous interface for file-backed storage providers.

    All methods are async and return Awaitable types. Implementations should
    avoid blocking the event loop by using asyncio.to_thread() for I/O or
    native async libraries.

    Implementations must operate relative to an optional root directory and
    should avoid allowing traversal outside their configured scope.
    """

    @abstractmethod
    async def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a new file or directory asynchronously.

        Args:
            path: Target backend path relative to the backend root.
            data: Optional content for file creation. Ignored for directories.
            is_directory: Create a directory when True.
            overwrite: Replace existing files if True.

        Returns:
            FileInfo describing the newly created resource.

        """

    @abstractmethod
    async def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Retrieve file contents asynchronously.

        Args:
            path: Target file path relative to the backend root.
            binary: When False, content should be decoded as UTF-8 text.

        Returns:
            File contents as bytes or str depending on binary flag.

        """

    @abstractmethod
    async def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Modify an existing file asynchronously.

        Args:
            path: Target file path relative to the backend root.
            data: New content to write.
            append: Append to the existing content when True.

        Returns:
            FileInfo describing the updated resource.

        """

    @abstractmethod
    async def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Remove a file or directory asynchronously.

        Args:
            path: Target path relative to the backend root.
            recursive: Allow recursive deletion of non-empty directories.

        """

    @abstractmethod
    async def info(self, path: PathLike) -> FileInfo:
        """Retrieve metadata about a path asynchronously.

        Args:
            path: Target path relative to the backend root.

        Returns:
            FileInfo with metadata about the path.

        """

    @abstractmethod
    async def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = 8192,
        binary: bool = True,
    ) -> AsyncIterator[bytes | str]:
        """Stream file contents in chunks asynchronously.

        Args:
            path: Target file path relative to the backend root.
            chunk_size: Number of bytes to read per iteration.
            binary: When False, chunks should be decoded as UTF-8 text.

        Yields:
            Chunks of file content as bytes or str depending on binary flag.

        """

    @abstractmethod
    async def stream_write(
        self,
        path: PathLike,
        *,
        chunk_source: AsyncIterator[bytes | str] | BinaryIO,
        chunk_size: int = 8192,
        overwrite: bool = False,
    ) -> FileInfo:
        """Write file from async stream.

        Args:
            path: Target file path relative to the backend root.
            chunk_source: AsyncIterator or file-like object providing chunks.
            chunk_size: Chunk size hint (used when reading from sources).
            overwrite: Replace existing files if True.

        Returns:
            FileInfo describing the newly written resource.

        """

    @abstractmethod
    async def checksum(
        self,
        path: PathLike,
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> str:
        """Compute a file checksum asynchronously.

        Args:
            path: Target file path relative to the backend root.
            algorithm: Hashing algorithm to use. Supported values: md5, sha256,
                sha512, blake3.

        Returns:
            Hexadecimal string representation of the file's hash.

        """

    @abstractmethod
    async def checksum_many(
        self,
        paths: list[PathLike],
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> dict[str, str]:
        """Compute checksums for multiple files asynchronously.

        Args:
            paths: List of file paths relative to the backend root.
            algorithm: Hashing algorithm to use. Supported values: md5, sha256,
                sha512, blake3.

        Returns:
            Dictionary mapping path strings to hexadecimal hash values.
            Missing files are silently skipped and not included in the result.

        """

    @abstractmethod
    async def glob(
        self,
        pattern: str,
        *,
        include_dirs: bool = False,
    ) -> list[Path]:
        """Find paths matching a glob pattern asynchronously.

        Supports standard glob syntax including *, ?, and []. For recursive
        globbing, use ** in the pattern (e.g., '**/file.txt').

        Args:
            pattern: Glob pattern to match. Patterns are relative to the backend root.
            include_dirs: When False, only return files. When True, include directories.

        Returns:
            List of paths matching the pattern, relative to the backend root.
            Returns empty list if no matches found.

        """

    async def glob_files(
        self,
        pattern: str,
    ) -> list[Path]:
        """Find files matching a glob pattern asynchronously.

        Convenience method that calls glob() with include_dirs=False.

        Args:
            pattern: Glob pattern to match.

        Returns:
            List of file paths matching the pattern.

        """
        return await self.glob(pattern, include_dirs=False)

    async def glob_dirs(
        self,
        pattern: str,
    ) -> list[Path]:
        """Find directories matching a glob pattern asynchronously.

        Convenience method that returns only directories by filtering glob results.

        Args:
            pattern: Glob pattern to match.

        Returns:
            List of directory paths matching the pattern.

        """
        all_matches = await self.glob(pattern, include_dirs=True)
        # Filter to only directories by checking with info()
        dirs = []
        for path in all_matches:
            try:
                info_result = await self.info(path)
                if info_result.is_dir:
                    dirs.append(path)
            except FileBackendError:
                # Skip paths that can't be accessed
                pass
        return dirs


class AsyncSyncFileBackend(AsyncFileBackend):
    """Extended async backend interface supporting bidirectional synchronisation."""

    @abstractmethod
    async def push(self, *, message: str | None = None) -> None:
        """Publish local changes to the remote data source asynchronously."""

    @abstractmethod
    async def pull(self) -> None:
        """Retrieve remote updates into the local workspace asynchronously."""

    async def sync(self) -> None:
        """Perform a pull followed by a push asynchronously."""
        await self.pull()
        await self.push()

    @abstractmethod
    async def conflict_report(self) -> list[SyncConflict]:
        """Return the set of outstanding synchronisation conflicts."""

    @abstractmethod
    async def conflict_accept_local(self, path: PathLike) -> None:
        """Resolve a conflict by keeping the local version."""

    @abstractmethod
    async def conflict_accept_remote(self, path: PathLike) -> None:
        """Resolve a conflict by keeping the remote version."""

    @abstractmethod
    async def conflict_resolve(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
    ) -> None:
        """Resolve a conflict by supplying a new version of the file."""


# Import SyncConflict for type hinting
from .interfaces import SyncConflict  # noqa: E402, F401
