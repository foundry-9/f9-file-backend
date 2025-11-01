"""Asynchronous OpenAI vector store backend implementation.

This module provides async variants of OpenAIVectorStoreFileBackend operations
using asyncio.to_thread() for blocking API calls and filesystem operations.

Key Features:
    - Non-blocking OpenAI API calls via asyncio.to_thread()
    - Full compatibility with AsyncFileBackend interface
    - Same OpenAI vector store features as OpenAIVectorStoreFileBackend
    - Suitable for concurrent remote storage operations

Performance Characteristics:
    - Non-blocking, suitable for concurrent operations
    - Thread pool executor handles API calls
    - Network I/O for all operations
    - Suitable for I/O-bound concurrent workloads with OpenAI API

Example:

    >>> import asyncio
    >>> import openai
    >>> from f9_file_backend import AsyncOpenAIVectorStoreFileBackend
    >>>
    >>> async def main():
    ...     client = openai.AsyncOpenAI(api_key="sk-...")
    ...     backend = AsyncOpenAIVectorStoreFileBackend(
    ...         client=client,
    ...         vector_store_id="vs_...",
    ...         cache_ttl=300,
    ...         purpose="assistants"
    ...     )
    ...     await backend.create("doc.txt", data=b"Content")
    ...     content = await backend.read("doc.txt")
    ...     print(content)
    ...
    >>> asyncio.run(main())

See Also:
    - AsyncFileBackend: Abstract async interface
    - OpenAIVectorStoreFileBackend: Synchronous implementation
    - AsyncLocalFileBackend: Async local filesystem backend

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
from .openai_backend import OpenAIVectorStoreFileBackend

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


class AsyncOpenAIVectorStoreFileBackend(AsyncFileBackend):
    """Asynchronous OpenAI vector store backend implementation.

    Uses asyncio.to_thread() to run blocking OpenAI API calls in a thread pool,
    allowing the event loop to remain responsive for concurrent operations.
    """

    def __init__(
        self,
        *,
        client: any = None,  # openai.OpenAI
        vector_store_id: str,
        api_key: str | None = None,
        cache_ttl: int = 300,
        purpose: str = "assistants",
    ) -> None:
        """Initialise the async OpenAI backend.

        Args:
            client: OpenAI client instance (optional if api_key provided).
            vector_store_id: ID of the vector store to use (required).
            api_key: OpenAI API key (required if client not provided).
            cache_ttl: Cache time-to-live in seconds for directory listings.
            purpose: Purpose for the vector store (default: "assistants").

        Raises:
            ValueError: If vector_store_id is missing.

        """
        if not vector_store_id:
            message = "vector_store_id parameter is required"
            raise ValueError(message)

        # Construct connection_info dict for the sync backend
        connection_info: dict[str, object] = {
            "vector_store_id": vector_store_id,
            "cache_ttl": cache_ttl,
            "purpose": purpose,
        }

        if api_key is not None:
            connection_info["api_key"] = api_key

        self._sync_backend = OpenAIVectorStoreFileBackend(
            connection_info,
            client=client,
        )

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
