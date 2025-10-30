"""Asynchronous Git-backed synchronised file backend implementation.

This module provides async variants of GitSyncFileBackend operations using
asyncio.to_thread() for blocking Git and filesystem operations.

Key Features:
    - Non-blocking Git operations via asyncio.to_thread()
    - Asynchronous push/pull/sync operations
    - Full compatibility with AsyncSyncFileBackend interface
    - Same Git features as GitSyncFileBackend

Performance Characteristics:
    - Non-blocking, suitable for concurrent operations
    - Thread pool executor handles Git subprocesses
    - Network I/O for push operations
    - Suitable for I/O-bound concurrent workloads with Git

Example:

    >>> import asyncio
    >>> from f9_file_backend import AsyncGitSyncFileBackend
    >>>
    >>> async def main():
    ...     backend = AsyncGitSyncFileBackend(
    ...         root="/data/repo",
    ...         git_config={"user.name": "Bot", "user.email": "bot@example.com"},
    ...         auto_commit=True
    ...     )
    ...     await backend.create("README.md", data=b"# Project")
    ...     await backend.push()
    ...     conflicts = await backend.conflict_report()
    ...     print(f"Conflicts: {conflicts}")
    >>>
    >>> asyncio.run(main())

See Also:
    - AsyncSyncFileBackend: Abstract async sync interface
    - GitSyncFileBackend: Synchronous implementation
    - AsyncLocalFileBackend: Async local filesystem backend

"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, BinaryIO

from .async_interfaces import AsyncSyncFileBackend
from .git_backend import GitSyncFileBackend
from .interfaces import (
    ChecksumAlgorithm,
    FileInfo,
    PathLike,
    SyncConflict,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping
    from pathlib import Path


class AsyncGitSyncFileBackend(AsyncSyncFileBackend):
    """Asynchronous Git-backed synchronised file backend implementation.

    Uses asyncio.to_thread() to run blocking Git operations and filesystem
    I/O in a thread pool, allowing the event loop to remain responsive.
    """

    def __init__(
        self,
        root: PathLike | None = None,
        *,
        git_config: Mapping[str, str] | None = None,
        auto_commit: bool = True,
        auto_push: bool = False,
        create_root: bool = True,
    ) -> None:
        """Initialise the async Git backend.

        Args:
            root: Root directory for the Git repository.
            git_config: Git configuration key-value pairs.
            auto_commit: Automatically commit file operations.
            auto_push: Automatically push to remote after commits.
            create_root: Create root directory if it doesn't exist.

        """
        self._sync_backend = GitSyncFileBackend(
            root=root,
            git_config=git_config,
            auto_commit=auto_commit,
            auto_push=auto_push,
            create_root=create_root,
        )

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
        """Stream file contents in chunks asynchronously."""

        async def _stream_async() -> AsyncIterator[bytes | str]:
            """Internal async generator for streaming."""
            iterator = await asyncio.to_thread(
                self._sync_backend.stream_read,
                path,
                chunk_size=chunk_size,
                binary=binary,
            )
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
        """Write file from async stream asynchronously."""
        if hasattr(chunk_source, "read"):
            chunks = chunk_source
        elif hasattr(chunk_source, "__aiter__"):
            chunks_list: list[bytes | str] = []
            async for chunk in chunk_source:  # type: ignore
                chunks_list.append(chunk)
            chunks = iter(chunks_list)
        else:
            chunks = chunk_source

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

    async def push(self, *, message: str | None = None) -> None:
        """Publish local changes to the remote data source asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.push,
            message=message,
        )

    async def pull(self) -> None:
        """Retrieve remote updates into the local workspace asynchronously."""
        return await asyncio.to_thread(
            self._sync_backend.pull,
        )

    async def conflict_report(self) -> list[SyncConflict]:
        """Return the set of outstanding synchronisation conflicts."""
        return await asyncio.to_thread(
            self._sync_backend.conflict_report,
        )

    async def conflict_accept_local(self, path: PathLike) -> None:
        """Resolve a conflict by keeping the local version."""
        return await asyncio.to_thread(
            self._sync_backend.conflict_accept_local,
            path,
        )

    async def conflict_accept_remote(self, path: PathLike) -> None:
        """Resolve a conflict by keeping the remote version."""
        return await asyncio.to_thread(
            self._sync_backend.conflict_accept_remote,
            path,
        )

    async def conflict_resolve(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
    ) -> None:
        """Resolve a conflict by supplying a new version of the file."""
        return await asyncio.to_thread(
            self._sync_backend.conflict_resolve,
            path,
            data=data,
        )

    def sync_session(
        self,
        *,
        timeout: float | None = None,
    ):
        """Create a context manager for atomic synchronisation operations.

        For the async git backend, returns the synchronous context manager
        from the underlying GitSyncFileBackend. The caller should use it as a
        regular context manager (not async context manager).

        Args:
            timeout: Optional timeout in seconds for acquiring the lock.

        Returns:
            Context manager that acquires and releases the lock.

        Raises:
            TimeoutError: If the lock cannot be acquired within the timeout.

        Note:
            This method is NOT async. Use it in a regular with statement:

            with backend.sync_session():
                # perform operations

        """
        return self._sync_backend.sync_session(timeout=timeout)
