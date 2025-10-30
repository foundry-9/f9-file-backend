"""Asynchronous local filesystem backend implementation.

This module provides async variants of LocalFileBackend operations using
asyncio.to_thread() for I/O operations to avoid blocking the event loop.

Key Features:
    - Non-blocking file operations via asyncio.to_thread()
    - Async streaming with AsyncIterator
    - Full compatibility with AsyncFileBackend interface
    - Same filesystem features as LocalFileBackend

Performance Characteristics:
    - Non-blocking, suitable for concurrent operations
    - Thread pool executor handles filesystem I/O
    - Memory-efficient streaming operations
    - Suitable for I/O-bound concurrent workloads

Example:

    >>> import asyncio
    >>> from f9_file_backend import AsyncLocalFileBackend
    >>> from pathlib import Path
    >>>
    >>> async def main():
    ...     backend = AsyncLocalFileBackend(root=Path("/data"))
    ...     await backend.create("file.txt", data=b"Hello!")
    ...     content = await backend.read("file.txt")
    ...     print(content)
    ...     await backend.delete("file.txt")
    >>>
    >>> asyncio.run(main())

See Also:
    - AsyncFileBackend: Abstract async interface
    - LocalFileBackend: Synchronous implementation
    - AsyncGitSyncFileBackend: Async Git backend

"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, BinaryIO

from .async_interfaces import AsyncFileBackend
from .interfaces import (
    ChecksumAlgorithm,
    FileInfo,
    PathLike,
)
from .local import LocalFileBackend

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


class AsyncLocalFileBackend(AsyncFileBackend):
    """Asynchronous local filesystem backend implementation.

    Uses asyncio.to_thread() to run blocking I/O operations in a thread pool,
    allowing the event loop to remain responsive for concurrent operations.
    """

    def __init__(
        self,
        root: PathLike | None = None,
        *,
        create_root: bool = True,
    ) -> None:
        """Initialise the async backend with the same root as LocalFileBackend.

        Args:
            root: Root directory path (defaults to current working directory).
            create_root: Create root directory if it doesn't exist.

        """
        self._sync_backend = LocalFileBackend(root=root, create_root=create_root)

    @property
    def root(self) -> Path:
        """Absolute path used as the backend root."""
        return self._sync_backend.root

    async def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a file or directory asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.create,
            path,
            data=data,
            is_directory=is_directory,
            overwrite=overwrite,
        )

    async def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Return file contents asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.read,
            path,
            binary=binary,
        )

    async def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Modify an existing file asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.update,
            path,
            data=data,
            append=append,
        )

    async def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Remove a file or directory asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.delete,
            path,
            recursive=recursive,
        )

    async def info(self, path: PathLike) -> FileInfo:
        """Retrieve metadata about a path asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.info,
            path,
        )

    async def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = 8192,
        binary: bool = True,
    ) -> AsyncIterator[bytes | str]:
        """Stream file contents in chunks asynchronously.

        Uses asyncio.to_thread() to perform blocking file I/O while yielding
        chunks, allowing the event loop to remain responsive.

        """

        async def _stream_async() -> AsyncIterator[bytes | str]:
            """Internal async generator for streaming."""
            # Run the sync streaming in a thread
            iterator = await asyncio.to_thread(
                self._sync_backend.stream_read,
                path,
                chunk_size=chunk_size,
                binary=binary,
            )
            # Yield chunks from the iterator
            for chunk in iterator:
                yield chunk

        return _stream_async()

    async def stream_write(
        self,
        path: PathLike,
        *,
        chunk_source: AsyncIterator[bytes | str] | BinaryIO,
        chunk_size: int = 8192,
        overwrite: bool = False,
    ) -> FileInfo:
        """Write file from async stream asynchronously.

        Collects chunks from the async iterator and writes them using
        the sync backend in a thread pool.

        """
        # Collect all chunks from async iterator or pass through BinaryIO
        if hasattr(chunk_source, "read"):
            # It's a BinaryIO - pass directly
            chunks = chunk_source
        elif hasattr(chunk_source, "__aiter__"):
            # It's an AsyncIterator
            chunks_list: list[bytes | str] = []
            async for chunk in chunk_source:  # type: ignore
                chunks_list.append(chunk)
            chunks = iter(chunks_list)
        else:
            # It's a regular iterator (sync)
            chunks = chunk_source

        # Write the collected chunks in a thread
        return await asyncio.to_thread(
            self._sync_backend.stream_write,
            path,
            chunk_source=chunks,
            chunk_size=chunk_size,
            overwrite=overwrite,
        )

    async def checksum(
        self,
        path: PathLike,
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> str:
        """Compute a file checksum asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.checksum,
            path,
            algorithm=algorithm,
        )

    async def checksum_many(
        self,
        paths: list[PathLike],
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> dict[str, str]:
        """Compute checksums for multiple files asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.checksum_many,
            paths,
            algorithm=algorithm,
        )

    async def glob(
        self,
        pattern: str,
        *,
        include_dirs: bool = False,
    ) -> list[Path]:
        """Find paths matching a glob pattern asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.glob,
            pattern,
            include_dirs=include_dirs,
        )
